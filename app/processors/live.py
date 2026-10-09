import json
import os
import subprocess
import sys
import threading
import time

from app.processors.video import VideoProcessor
from app.processors.translation import TranslationService
from app.processors.subtitles import SubtitleGenerator
from app.processors import vad
from app.config import settings
from app.core import _release_gpu_memory

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


class LiveTranslationEngine:
    POLL_INTERVAL_S = 0.5

    def __init__(self, video_path: str, source_lang: str, target_lang: str,
                 lookahead_seconds: float = 30.0,
                 chunk_overlap: float = None,
                 whisper_model: str = None, llm_model: str = None,
                 local_llm_file: str = None,
                 transcode_to_h264: bool = False, session_id: str = None):
        self.video_path = video_path
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.lookahead_seconds = lookahead_seconds
        self.chunk_seconds = 25.0
        self.chunk_overlap = chunk_overlap if chunk_overlap is not None else settings.LIVE_CHUNK_OVERLAP_SECONDS
        self._reported_position = 0.0
        self._reported_state = "Stopped"
        self.remuxed = False
        self.transcoding = transcode_to_h264
        self.transcode_progress = 0.0
        self.transcode_error = None
        # HLS event stream (growing playlist) — only used when transcode_to_h264.
        self.hls_ready = False
        self.hls_dir = os.path.join(settings.LIVE_REMUX_DIR, session_id) if session_id else None
        self._hls_proc = None

        self.video_processor = VideoProcessor()
        self.subtitle_generator = SubtitleGenerator()
        self.whisper_model = whisper_model
        self.llm_model = llm_model
        self.local_llm_file = local_llm_file
        self.translation_service = None
        self._whisper_proc = None
        self._models_ready = False

        self.duration = self.video_processor.get_duration(video_path)

        self.segments: list = []
        self._translation_context: list = []
        self.processed_until = 0.0
        self._stop_flag = False
        self._thread = None
        self._lock = threading.Lock()
        self.logs: list = []
        self._error = None
        self._consecutive_errors = 0
        self._max_consecutive_errors = 3
        self._last_update_time = time.time()
        self._last_logged_state = None
        self._hls_thread = None

        base = os.path.splitext(os.path.basename(video_path))[0]
        self.srt_file_path = os.path.join(settings.OUTPUT_DIR, f"{base}_live.{target_lang}.srt")

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._log(f"[Live] Live translation started (lookahead={self.lookahead_seconds}s, chunk={self.chunk_seconds}s)")

    def update_position(self, position: float, state: str):
        self._reported_position = position
        self._reported_state = state
        self._last_update_time = time.time()

    def stop(self):
        self._stop_flag = True
        if self._hls_proc and self._hls_proc.poll() is None:
            try:
                self._hls_proc.terminate()
            except Exception:
                pass
        if self._hls_thread and self._hls_thread.is_alive():
            self._hls_thread.join(timeout=5)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        self._translation_context = []
        self._release_models()
        self._log("[Live] Stopped")

    def _release_models(self):
        if self._whisper_proc is not None:
            try:
                self._whisper_proc.terminate()
                self._whisper_proc.wait(timeout=5)
            except Exception:
                try:
                    self._whisper_proc.kill()
                except Exception:
                    pass
            self._whisper_proc = None
        try:
            del self.translation_service
        except Exception:
            pass
        _release_gpu_memory()

    def _start_whisper_worker(self):
        model_arg = self.whisper_model if self.whisper_model else ""
        self._whisper_proc = subprocess.Popen(
            [sys.executable, "-m", "app.processors.whisper_worker", model_arg],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            cwd=PROJECT_ROOT,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        line = self._whisper_proc.stdout.readline()
        if not line:
            raise RuntimeError("Whisper worker failed to start (check backend logs)")
        resp = json.loads(line)
        if resp.get("type") != "ready":
            raise RuntimeError(f"Whisper worker failed to load model: {resp.get('message', 'unknown error')}")
        self._log(f"[Live] Whisper worker ready ({self.whisper_model or settings.LOCAL_WHISPER_MODEL})")

    def _whisper_call(self, wav_path: str, offset: float, language: str = None) -> list:
        req = {"cmd": "transcribe", "wav": wav_path, "offset": offset, "language": language}
        self._whisper_proc.stdin.write(json.dumps(req) + "\n")
        self._whisper_proc.stdin.flush()
        line = self._whisper_proc.stdout.readline()
        if not line:
            raise RuntimeError("Whisper worker terminated unexpectedly")
        resp = json.loads(line)
        if resp.get("type") == "error":
            raise RuntimeError(f"Whisper worker error: {resp.get('message')}")
        return resp.get("segments", [])

    def _load_models(self):
        self._log("[Live] Starting Whisper worker and loading translation model...")
        start_t = time.time()
        self._start_whisper_worker()
        self.translation_service = TranslationService(model=self.llm_model, local_file=self.local_llm_file)
        self._models_ready = True
        self._log(f"[Live] Models ready in {time.time() - start_t:.0f}s")

    def get_status(self) -> dict:
        with self._lock:
            processed_until = self.processed_until
            segments = list(self.segments)
            logs = self.logs[-50:]
            error = self._error
            srt_file_path = self.srt_file_path

        return {
            "state": self._reported_state,
            "current_position": self._reported_position,
            "duration": self.duration,
            "filepath": self.video_path,
            "processed_until": processed_until,
            "buffer_health_seconds": max(0, processed_until - self._reported_position),
            "segments": segments,
            "srt_file_path": srt_file_path,
            "remuxed": self.remuxed,
            "hls": self.transcoding,
            "playlist_ready": self.hls_ready,
            "transcoding": self.transcoding,
            "transcode_progress": self.transcode_progress,
            "transcode_error": self.transcode_error,
            "models_loading": not self._models_ready,
            "logs": logs,
            "error": error,
        }

    def _transcode(self):
        """Convert the source to H.264 as an HLS event stream in a background thread.
        Playlist grows as segments complete; playback can start after the first
        segment while the rest converts. ffmpeg outpaces 1x playback."""
        if not self.hls_dir:
            self._log("[Live] No HLS directory configured — skipping conversion")
            return
        os.makedirs(self.hls_dir, exist_ok=True)
        self._log("[Live] Source is not browser-playable — streaming to HLS (H.264), playback starts in a few seconds...")
        total_us = self.duration * 1_000_000 if self.duration and self.duration > 0 else None
        last_logged = 0.0

        attempts = [
            (["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "24"], "NVENC"),
            (["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"], "libx264"),
        ]
        proc = None
        try:
            for i, (vcodec_args, encoder_name) in enumerate(attempts):
                # All output paths RELATIVE and cwd=hls_dir: ffmpeg resolves the
                # fMP4 init filename against the CWD, not the segment dir, so a
                # bare name here keeps init.mp4/playlist/segments together and
                # the playlist's relative URIs resolve against our route URL.
                cmd = [
                    "ffmpeg", "-hide_banner", "-y",
                    "-i", self.video_path,
                    "-vf", "format=yuv420p",
                    *vcodec_args,
                    "-c:a", "aac", "-b:a", "192k",
                    "-g", "48", "-keyint_min", "48",
                    "-f", "hls",
                    "-hls_time", "4",
                    "-hls_playlist_type", "event",
                    "-hls_segment_type", "fmp4",
                    "-hls_flags", "independent_segments",
                    "-nostats", "-progress", "pipe:1",
                    "-hls_segment_filename", "seg%05d.m4s",
                    "playlist.m3u8",
                ]
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    text=True, encoding="utf-8", cwd=self.hls_dir,
                )
                self._hls_proc = proc
                last_pct = 0.0
                stopped = False
                for line in proc.stdout:
                    if self._stop_flag:
                        proc.terminate()
                        stopped = True
                        break
                    if line.startswith("out_time_ms="):
                        try:
                            done_us = float(line.split("=", 1)[1])
                        except ValueError:
                            continue
                        # Flip before the percentage math: if the duration probe
                        # returned <= 0 (total_us None) there is no percentage,
                        # but the playlist still becomes playable after ~4s of
                        # output and must not gate playback behind it.
                        if not self.hls_ready and done_us >= 4_000_000:
                            with self._lock:
                                self.hls_ready = True
                            self._log("[Live] HLS playlist ready — playback can start now")
                        if total_us:
                            pct = min(99.0, done_us / total_us * 100.0)
                            if pct - last_pct >= 2.0:
                                last_pct = pct
                                self.transcode_progress = pct
                                if pct - last_logged >= 10.0:
                                    last_logged = pct
                                    self._log(f"[Live] Conversion {pct:.0f}% done")
                if stopped:
                    return
                ret = proc.wait()
                if self._stop_flag:
                    return
                if ret == 0:
                    self.transcode_progress = 100.0
                    self._log("[Live] Conversion to H.264 complete")
                    return
                print(f"[Live] {encoder_name} HLS transcode failed (exit {ret})"
                      + (", falling back to libx264..." if i < len(attempts) - 1 else ""))
            self.transcode_error = "Conversion failed with all encoders — playback unavailable for this file, subtitles continue"
            self._log(f"[Live] {self.transcode_error}")
        except Exception as e:
            self.transcode_error = f"Video conversion error: {e}"
            self._log(f"[Live] HLS conversion error: {e}")
        finally:
            d, self._hls_proc = self._hls_proc, None
            if d and d.poll() is None:
                d.kill()

    def _run(self):
        # Transcode (for browser playback) runs in parallel — model loading and
        # transcription never wait for it since they read the source directly.
        if self.transcoding:
            self._hls_thread = threading.Thread(target=self._transcode, daemon=True)
            self._hls_thread.start()

        try:
            self._load_models()
        except Exception as e:
            self._error = f"Model loading failed: {e}"
            self._log(f"[Live] {self._error}")
            self._release_models()
            return

        while not self._stop_flag:
            try:
                if time.time() - self._last_update_time > settings.LIVE_SESSION_TIMEOUT_SECONDS:
                    self._log("[Live] No playback updates received, releasing session")
                    break

                position = self._reported_position
                state = self._reported_state
                if state in ('Stopped', 'Disconnected'):
                    if self._last_logged_state != state:
                        self._last_logged_state = state
                        self._log("[Live] Waiting for playback...")
                    time.sleep(self.POLL_INTERVAL_S)
                    continue

                self._last_logged_state = None

                target_until = position + self.lookahead_seconds

                with self._lock:
                    if position > self.processed_until + self.lookahead_seconds + self.chunk_seconds:
                        self.segments = [s for s in self.segments if s['start'] <= position]
                        self.processed_until = position
                        self._translation_context = []
                        self._log(f"[Live] Forward seek detected, resetting buffer to {position:.0f}s")

                with self._lock:
                    processed_until = self.processed_until
                if processed_until >= target_until or processed_until >= self.duration:
                    time.sleep(self.POLL_INTERVAL_S)
                    continue

                chunk_start = processed_until
                chunk_end = min(chunk_start + self.chunk_seconds, self.duration)
                self._log(f"[Live] Extracting {chunk_start:.0f}-{chunk_end:.0f}s")

                t0 = time.time()
                wav_path = self.video_processor.extract_audio_segment(self.video_path, chunk_start, chunk_end)
                if wav_path is None:
                    # Video-only source: nothing to transcribe, keep the session alive
                    with self._lock:
                        self.processed_until = chunk_end
                    self._log("[Live] No audio track in source — subtitles unavailable")
                    continue
                self._log(f"[Live] Audio extracted in {time.time() - t0:.1f}s")

                # Audio detection: skip the model entirely when the chunk is
                # silent — no transcription, no translation, no GPU work.
                try:
                    if vad.get_speech_regions(wav_path) == []:
                        with self._lock:
                            self.processed_until = chunk_end
                        self._log(f"[Live] Chunk {chunk_start:.0f}-{chunk_end:.0f}s is silent — skipped")
                        continue
                except Exception as vad_err:
                    self._log(f"[Live] Silence check failed ({vad_err}) — transcribing chunk anyway")

                t1 = time.time()
                try:
                    new_segs = self._whisper_call(wav_path, chunk_start, language=self.source_lang)
                finally:
                    if os.path.exists(wav_path):
                        os.remove(wav_path)
                self._log(f"[Live] Transcribed in {time.time() - t1:.1f}s")

                self._consecutive_errors = 0

                with self._lock:
                    existing = list(self.segments)
                deduped = self._dedup(new_segs, existing)

                if not deduped:
                    with self._lock:
                        self.processed_until = chunk_end
                    self._log(f"[Live] No new speech in chunk {chunk_start:.0f}-{chunk_end:.0f}s")
                    continue

                translated = self.translation_service.translate_chunk(
                    deduped, self.source_lang, self.target_lang,
                    context=self._translation_context
                )

                with self._lock:
                    self.segments.extend(translated)
                    self.segments.sort(key=lambda s: s['start'])
                    self.processed_until = chunk_end
                    # Rolling context for the next chunk: recent (source,
                    # translation) pairs, skipping failed translations.
                    for seg, out in zip(deduped, translated):
                        if not (out.get('text') or '').startswith('[Error'):
                            self._translation_context.append((seg['text'], out['text']))
                    self._translation_context = self._translation_context[-settings.LLM_CONTEXT_LINES:]
                    self._write_srt()

                buffer_health = self.processed_until - position
                self._log(f"[Live] Translated {len(translated)} segments, buffer {buffer_health:.0f}s ahead")
            except Exception as e:
                self._consecutive_errors += 1
                self._error = str(e)
                self._log(f"[Live] Error ({self._consecutive_errors}/{self._max_consecutive_errors}): {e}")
                if self._consecutive_errors >= self._max_consecutive_errors:
                    self._log("[Live] Fatal: repeated failures, releasing GPU memory")
                    break
                time.sleep(2.0)

        heartbeat_stale = time.time() - self._last_update_time > settings.LIVE_SESSION_TIMEOUT_SECONDS
        if self._consecutive_errors >= self._max_consecutive_errors or heartbeat_stale:
            self._release_models()

    def _dedup(self, new_segs: list, existing_segs: list) -> list:
        deduped = []
        for seg in new_segs:
            overlaps = False
            for ex in existing_segs:
                if seg['start'] < ex['end'] and seg['end'] > ex['start']:
                    overlaps = True
                    break
            if not overlaps:
                deduped.append(seg)
        return deduped

    def _write_srt(self):
        content = self.subtitle_generator.generate_srt(self.segments)
        tmp_path = self.srt_file_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, self.srt_file_path)

    def _log(self, msg):
        self.logs = self.logs[-199:]
        self.logs.append(msg)
        print(msg)
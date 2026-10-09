import os
import re
import subprocess
import ffmpeg
from app.config import settings

class VideoProcessor:
    def validate_video(self, filepath: str) -> bool:
        """
        Validates if the file exists and is a valid video file.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")

        try:
            probe = ffmpeg.probe(filepath)
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)

            if not video_stream:
                raise ValueError("No video stream found in file.")

            # Warning: Some videos might not have audio, but for this app it's critical
            if not audio_stream:
                raise ValueError("No audio stream found in file.")

            return True
        except ffmpeg.Error as e:
            raise ValueError(f"Invalid video file: {e.stderr.decode() if e.stderr else str(e)}")

    def probe_audio_quality(self, video_path: str, sample_seconds: float = 30.0) -> dict:
        """
        Cheap audio-quality probe to decide if the source needs denoising.
        Samples the first N seconds with silencedetect (at the configured noise
        floor threshold) + volumedetect, then reports:
          - silence_fraction: fraction of the window quieter than the threshold
            (~0 means the noise floor sits above the threshold = noisy)
          - mean_volume_db / max_volume_db from volumedetect
          - noisy: bool decision (no quiet moment found + audible mean level)

        # ponytail: single-heuristic probe (silence detection). If it
        # misjudges music-only content, pre-set AUDIO_ENHANCE=on/off instead
        # of adding spectral analysis.
        """
        duration = self.get_duration(video_path)
        window = max(sample_seconds, 1) if duration <= 0 else min(sample_seconds, duration)
        threshold = settings.AUDIO_PROBE_NOISE_FLOOR_DB
        try:
            audio = ffmpeg.input(video_path, ss=0, t=window).audio
            audio = audio.filter("silencedetect", noise=f"{threshold}dB", d="0.5").filter("volumedetect")
            _, stderr = (
                ffmpeg
                .output(audio, "null", f="null")
                .run(capture_stdout=True, capture_stderr=True)
            )
            log = stderr.decode("utf-8", errors="replace")

            silence_starts = re.findall(r"silence_start: ([\d.]+)", log)
            silence_ends = re.findall(r"silence_end: ([\d.]+)", log)
            silence_total = 0.0
            for i, s in enumerate(silence_starts):
                # Last silence may outlive the sample window
                e = float(silence_ends[i]) if i < len(silence_ends) else window
                silence_total += max(0.0, e - float(s))
            silence_fraction = min(1.0, silence_total / window)

            mean_match = re.search(r"mean_volume: (-?[\d.]+) dB", log)
            max_match = re.search(r"max_volume: (-?[\d.]+) dB", log)
            mean_db = float(mean_match.group(1)) if mean_match else 0.0
            max_db = float(max_match.group(1)) if max_match else 0.0

            noisy = silence_fraction < 0.01 and mean_db > -60.0
            return {
                "silence_fraction": silence_fraction,
                "mean_volume_db": mean_db,
                "max_volume_db": max_db,
                "noisy": noisy,
                "window": window,
                "threshold_db": threshold,
            }
        except ffmpeg.Error as e:
            # Probe failure must never block the pipeline — treat as clean
            # (previous behavior) and say so.
            print(f"[Video] Audio probe failed, skipping enhancement: "
                  f"{e.stderr.decode() if e.stderr else str(e)}")
            return {"silence_fraction": 1.0, "mean_volume_db": -120.0,
                    "max_volume_db": -120.0, "noisy": False, "window": 0,
                    "threshold_db": threshold}

    def extract_audio(self, video_path: str, enhance: str = None, normalize: bool = True) -> str:
        """
        Extracts audio from video and applies pre-processing filters.
        Whisper was trained on noisy audio, so aggressive denoising is opt-in
        via `enhance`: 'auto' probes the source and denoises only noisy audio
        (settings.AUDIO_ENHANCE); 'on' forces it; 'off' never.
        Highpass (rumble) + loudnorm always run.
        """
        if enhance is None:
            enhance = settings.AUDIO_ENHANCE

        denoise = False
        if enhance == "on":
            denoise = True
        elif enhance == "auto":
            probe = self.probe_audio_quality(video_path)
            denoise = probe["noisy"]
            print(f"[Video] Audio probe: window={probe['window']:.0f}s "
                  f"silence@{probe['threshold_db']}dB={probe['silence_fraction']:.2f} "
                  f"mean={probe['mean_volume_db']:.1f}dB -> "
                  f"{'noisy -> denoise chain' if denoise else 'clean -> standard chain'}")

        filename = os.path.splitext(os.path.basename(video_path))[0]
        output_path = os.path.join(settings.TEMP_DIR, f"{filename}.wav")

        if self.probe_codecs(video_path)["audio_codec"] is None:
            raise RuntimeError("No audio track in this video — nothing to transcribe.")

        try:
            input_node = ffmpeg.input(video_path)
            audio = input_node.audio

            audio = audio.filter("highpass", f=100)
            if denoise:
                # Duck constant background hiss/hum; acompressor lifts quiet
                # speech that noise-buries without reshaping dynamics wildly.
                audio = audio.filter("afftdn", nf=-25).filter("acompressor",
                                                              threshold="-25dB",
                                                              ratio=3)
            if normalize:
                audio = audio.filter("loudnorm")

            (
                ffmpeg
                .output(audio, output_path, acodec='pcm_s16le', ac=1, ar='16k')
                .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
            )
            return output_path
        except ffmpeg.Error as e:
            raise RuntimeError(f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")

    def extract_audio_segment(self, video_path: str, start: float, end: float,
                              output_path: str = None) -> str:
        """Extract a segment of audio [start, end] in seconds.
        Outputs 16kHz mono PCM WAV with NO denoise/normalize (speed priority).
        Uses ffmpeg -ss <start> -t <duration> for fast seeking.
        If output_path is None, generates a temp file in settings.TEMP_DIR.
        return path to the WAV file, or None when the source has no audio stream."""
        if output_path is None:
            output_path = os.path.join(settings.TEMP_DIR, f"chunk_{start}_{end}.wav")
        if self.probe_codecs(video_path)["audio_codec"] is None:
            return None  # video-only source; callers skip transcription
        try:
            (
                ffmpeg
                .input(video_path, ss=start, t=(end - start))
                .output(output_path, acodec='pcm_s16le', ac=1, ar='16k')
                .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
            )
            return output_path
        except ffmpeg.Error as e:
            raise RuntimeError(f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")

    def get_duration(self, video_path: str) -> float:
        """
        Returns the duration of the video in seconds.
        """
        try:
            probe = ffmpeg.probe(video_path)
            return float(probe['format']['duration'])
        except (ffmpeg.Error, KeyError, ValueError):
            return 0.0

    def burn_subtitles(self, video_path: str, subtitles_path: str, output_path: str, 
                       font: str = "Arial", font_size: int = 24, position: str = "Bottom Center", 
                       shadow: float = 1.0, outline: float = 1.0, use_gpu: bool = False) -> str:
        """
        Re-encodes the video with burnt-in subtitles.
        If use_gpu is True, attempts NVENC codecs (AV1 > HEVC > H.264). Falls back to libx264 (CPU).
        """
        # Map friendly position names to ASS alignment values
        numpad_align = {
            "Bottom Left": 1, "Bottom Center": 2, "Bottom Right": 3,
            "Left Center": 4, "Center": 5, "Right Center": 6,
            "Top Left": 7, "Top Center": 8, "Top Right": 9
        }
        
        alignment = numpad_align.get(position, 2)
        
        # Build force_style string
        # Warning: Windows paths in ffmpeg filter require escaping.
        # It's safer to use forward slashes for the path in the filter string.
        subs_path_safe = subtitles_path.replace("\\", "/").replace(":", "\\:")

        style = f"FontName={font},FontSize={font_size},Alignment={alignment},Outline={outline},Shadow={shadow}"
        
        def run_ffmpeg(vcodec, **extra):
            stream = ffmpeg.input(video_path)
            kwargs = {
                'vf': f"subtitles='{subs_path_safe}':force_style='{style}'",
                'vcodec': vcodec,
                'acodec': 'aac'
            }
            kwargs.update(extra)
            (
                stream
                .output(output_path, **kwargs)
                .run(overwrite_output=True, quiet=False)
            )

        try:
            if use_gpu:
                codecs = [c.strip() for c in settings.GPU_CODEC_CHAIN.split(",")]
                for codec in codecs:
                    try:
                        print(f"[Video] Attempting encoding with {codec} for: {os.path.basename(output_path)}")
                        if "nvenc" in codec:
                            run_ffmpeg(codec, preset="p5")
                        else:
                            run_ffmpeg(codec)
                        print(f"[Video] {codec} encoding successful.")
                        return output_path
                    except Exception as e:
                        msg = str(e)
                        if isinstance(e, ffmpeg.Error) and e.stderr:
                            msg = e.stderr.decode()
                        print(f"[Video] {codec} failed: {msg}. Trying next codec...")
                print("[Video] All GPU codecs failed. Falling back to CPU encoding (libx264)...")
            
            # CPU fallback or default
            print(f"[Video] Starting CPU encoding (libx264) for: {os.path.basename(output_path)}")
            run_ffmpeg('libx264')
            print("[Video] CPU encoding successful.")
            return output_path
            
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            print(f"FFmpeg burn-in fatal error: {error_msg}")
            raise RuntimeError(f"Failed to burn subtitles: {error_msg}")

    def probe_codecs(self, video_path: str) -> dict:
        """Use ffprobe to return codec info.
        Returns: {"video_codec": "h264", "audio_codec": "aac", "container": "mp4", "duration": 1440.5}
        Raises RuntimeError on probe failure."""
        try:
            probe = ffmpeg.probe(video_path)
            video_codec = None
            audio_codec = None
            for stream in probe['streams']:
                if stream['codec_type'] == 'video' and video_codec is None:
                    video_codec = stream['codec_name']
                elif stream['codec_type'] == 'audio' and audio_codec is None:
                    audio_codec = stream['codec_name']
            if not video_codec:
                raise RuntimeError("No video stream found in file.")
            try:
                duration = float(probe['format'].get('duration', 0))
            except (ValueError, TypeError):
                duration = 0.0
            container = os.path.splitext(video_path)[1].lower().lstrip('.')
            return {
                "video_codec": video_codec,
                "audio_codec": audio_codec,
                "container": container,
                "duration": duration
            }
        except (ffmpeg.Error, KeyError) as e:
            raise RuntimeError(f"Failed to probe video: {e}")

    def is_browser_playable(self, video_path: str) -> tuple:
        """Check if the video can be served directly to a browser <video> element.
        Returns: (can_play_directly: bool, needs_remux: bool, reason: str)
        - MP4 + H.264 + AAC → (True, False, "")
        - MKV + H.264 + AAC → (False, True, "Remux to MP4 required")
        - Any + HEVC/VP9/AV1 → (False, False, "Codec 'hevc' is not supported in browsers")
        - WebM + VP8/VP9 → (True, False, "")  # WebM is browser-native
        """
        info = self.probe_codecs(video_path)
        video_codec = info["video_codec"]
        audio_codec = info["audio_codec"]
        container = info["container"]

        supported_video = {'h264', 'vp8', 'vp9'}
        if video_codec not in supported_video:
            return (False, False, f"Codec '{video_codec}' is not supported in browsers. Use batch mode or convert to H.264 first.")

        if video_codec == 'h264':
            # None audio codec = no audio track, which browsers play fine as silence
            if audio_codec in {None, 'aac', 'mp3', 'opus', 'vorbis'}:
                if container in {'mp4', 'webm'}:
                    return (True, False, "")
                else:
                    return (False, True, "Remux to MP4 required")
            return (False, False, f"Unsupported audio codec '{audio_codec}' in container '{container}'")

        if video_codec in {'vp8', 'vp9'} and container == 'webm':
            return (True, False, "")

        return (False, False, f"Unsupported video codec '{video_codec}' in container '{container}'")

    def remux_to_mp4(self, video_path: str, output_path: str = None) -> str:
        """Remux container to MP4 without re-encoding (ffmpeg -c copy -movflags +faststart).
        If output_path is None, generates temp file in settings.TEMP_DIR.
        Returns path to the remuxed MP4 file.
        Raises RuntimeError on failure."""
        if output_path is None:
            output_path = os.path.join(settings.TEMP_DIR, f"{os.path.splitext(os.path.basename(video_path))[0]}_remux.mp4")
        try:
            (
                ffmpeg
                .input(video_path)
                .output(output_path, c="copy", movflags="+faststart")
                .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
            )
            return output_path
        except ffmpeg.Error as e:
            raise RuntimeError(f"FFmpeg remux error: {e.stderr.decode() if e.stderr else str(e)}")

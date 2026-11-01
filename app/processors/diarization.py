from typing import Any, Dict, List, Optional, Tuple
from app.config import settings
try:
    from pyannote.audio import Pipeline
    import torch
except Exception as e:
    Pipeline = None
    print(f"Warning: Could not load Diarization dependencies (pyannote.audio/torch). Diarization will be disabled. Error: {e}")

class DiarizationService:
    def __init__(self, auth_token: str = None):
        self.auth_token = auth_token or settings.HF_TOKEN
        self.pipeline = None
        self.exclusive_turns: List[Dict[str, Any]] = []
        if Pipeline and self.auth_token:
            try:
                self.pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-community-1",
                    token=self.auth_token
                )
                if torch.cuda.is_available():
                    self.pipeline.to(torch.device("cuda"))
            except Exception as e:
                print(f"Failed to load pyannote pipeline: {e}")

    def diarize(self, audio_path: str) -> List[Dict[str, Any]]:
        """
        Identifies speaker turns in the audio using pyannote's *exclusive*
        speaker diarization: turns never overlap, which is exactly the signal
        subtitle lines need (one voice per time span). Also stored on the
        instance as `self.exclusive_turns` for the word-level splitter.
        Returns a start-sorted list of {start, end, speaker}, or [] when
        diarization is unavailable (missing deps/token) — callers must
        tolerate [].
        """
        self.exclusive_turns = []
        if not self.pipeline:
            if not (self.auth_token and Pipeline):
                print("[Diarization] Unavailable — needs pyannote.audio deps and a "
                      "Hugging Face token (Settings) with accepted model terms. "
                      "Continuing without speaker separation.")
            return []

        # pyannote 4.x decodes file paths via torchcodec, which needs FFmpeg
        # shared libraries that are rarely present on Windows (winget builds
        # ship no DLLs). Decode the WAV ourselves and pass the waveform dict —
        # a documented pyannote input type.
        try:
            input_audio: object = audio_path
            try:
                from faster_whisper.audio import decode_audio
                waveform = decode_audio(audio_path, sampling_rate=16000)
                input_audio = {
                    "waveform": torch.from_numpy(waveform).unsqueeze(0).float(),
                    "sample_rate": 16000
                }
            except ImportError:
                pass  # faster-whisper missing → file path (torchcodec decode)
            output = self.pipeline(input_audio)
            turns_src = getattr(output, "exclusive_speaker_diarization", None)
            if turns_src is None:  # legacy pipeline output is the annotation itself
                turns_src = output

            segments: List[Dict[str, Any]] = []
            for turn, _, speaker in turns_src.itertracks(yield_label=True):
                segments.append({
                    "start": float(turn.start),
                    "end": float(turn.end),
                    "speaker": speaker
                })
            segments.sort(key=lambda s: s["start"])
            self.exclusive_turns = segments
            speakers = sorted({s["speaker"] for s in segments})
            shown = ", ".join(speakers[:8]) + ("..." if len(speakers) > 8 else "")
            print(f"[Diarization] {len(segments)} turn(s) across {len(speakers)} "
                  f"distinct speaker(s): {shown}")
            return segments
        except Exception as e:
            print(f"[Diarization] Failed: {e} — continuing without speaker separation.")
            return []

    @staticmethod
    def _turn_overlap(a_start: float, a_end: float, turn: Dict[str, Any]) -> float:
        return max(0.0, min(a_end, turn["end"]) - max(a_start, turn["start"]))

    def assign_speakers(self, transcript_segments: List[Dict[str, Any]],
                        diarization_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Assigns the most likely speaker to each transcript segment by maximal
        temporal overlap with the speaker turns (a segment straddling a
        handoff gets the speaker who held most of it, instead of the old
        midpoint match). Segment stays unlabeled when no turn overlaps it.
        """
        if not diarization_segments:
            return transcript_segments

        for t_seg in transcript_segments:
            best_speaker, best_overlap = None, 0.0
            for turn in diarization_segments:
                overlap = self._turn_overlap(t_seg['start'], t_seg['end'], turn)
                if overlap > best_overlap:
                    best_overlap, best_speaker = overlap, turn['speaker']
            if best_speaker is not None:
                t_seg['speaker'] = best_speaker
        return transcript_segments

    def split_segments_at_speaker_changes(self,
                                          transcript_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Re-groups each segment's words by speaker (from `diarize()`'s turns)
        so a subtitle line never contains two voices. Requires word
        timestamps (WHISPER_WORD_TIMESTAMPS=True): wordless segments pass
        through whole under their assigned speaker. Per-span text is rebuilt
        from the words and must match the original segment text — the
        fidelity guard against tokenization drift — otherwise the segment is
        left intact.

        Boundary rule: a word straddling two turns goes to the speaker with
        the larger temporal overlap (ties go to the earlier turn). A word
        overlapping no turn inherits the previous word's speaker. Each child
        is one maximal consecutive run of same-speaker words and carries only
        that run's words, so A→B→A yields three children, not two.
        """
        if not transcript_segments:
            return transcript_segments

        from app.processors.subtitles import is_cjk_char

        def join_words(words: List[Dict[str, Any]]) -> str:
            # Words arrive whitespace-stripped ("Hello", "、"). Spaces go back
            # only between non-CJK neighbors; CJK glues like the source text.
            out = ""
            for w in words:
                tok = w["word"]
                if out and not (is_cjk_char(out[-1]) or is_cjk_char(tok[:1] or " ")):
                    out += " "
                out += tok
            return out

        out: List[Dict[str, Any]] = []
        for seg in transcript_segments:
            words = seg.get('words') or []
            if len(words) < 2:
                out.append(seg)
                continue

            # A speaker for every word; the previous word's speaker carries
            # over through tiny gaps (turn edges vs word-timestamp jitter).
            labels: List[Optional[str]] = []
            prev = None
            for w in words:
                speaker, best_overlap = None, 0.0
                for turn in self.exclusive_turns:
                    overlap = self._turn_overlap(w['start'], w['end'], turn)
                    if overlap > best_overlap:
                        best_overlap, speaker = overlap, turn['speaker']
                labels.append(speaker if speaker is not None else prev)
                prev = labels[-1]

            if any(l is None for l in labels) or len(set(labels)) <= 1:
                out.append(seg)
                continue

            runs: List[Tuple[str, List[Dict[str, Any]]]] = []
            start = 0
            for i in range(1, len(labels)):
                if labels[i] != labels[i - 1]:
                    runs.append((labels[start], words[start:i]))
                    start = i
            runs.append((labels[start], words[start:]))

            pieces: Optional[List[Tuple[str, str, List[Dict[str, Any]]]]] = []
            for speaker, run in runs:
                text_part = join_words(run)
                if text_part not in seg['text']:
                    pieces = None  # cannot split the text faithfully
                    break
                pieces.append((speaker, text_part, run))
            if not pieces:
                out.append(seg)
                continue

            for speaker, text_part, run in pieces:
                child = dict(seg)
                child.update({
                    "start": run[0]['start'], "end": run[-1]['end'],
                    "text": text_part, "speaker": speaker,
                    "words": run,
                })
                out.append(child)
        out.sort(key=lambda s: s["start"])
        return out

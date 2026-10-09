"""Qwen3-ASR transcription engine (alternative to Whisper).

Uses the official `qwen-asr` package (Transformers backend) with
Qwen/Qwen3-ASR-1.7B for transcription and Qwen/Qwen3-ForcedAligner-0.6B for
word-level timestamps. Both are optional dependencies: the default Whisper
path keeps working without them.

Pipeline (docs/TRANSCRIPTION_PIPELINE.md, Qwen section):
  1. Silero VAD finds speech regions (app/processors/vad.py) — silence is
     never sent to the model.
  2. Speech regions are grouped into small windows (≤ QWEN_MAX_WINDOW_SECONDS).
  3. Windows are batch-transcribed; the ForcedAligner provides word
     timestamps inside each window, grouped into subtitle segments whose
     timings match the Whisper segment dict shape (start/end/text/words).
  4. Timestamps are absolute: chunk offset + window offset + aligner time.

Limitation surfaced to the operator, never silently hidden: the aligner
supports 11 languages. Other languages still transcribe, but word timestamps
fall back to window boundaries and a clear message is printed.
"""
import os
import numpy as np
from typing import Dict, List, Optional, Tuple

from app.config import settings
from app.cuda import fix_cuda_paths
from app.processors import vad

SAMPLE_RATE = vad.SAMPLE_RATE

# ISO-639-1 (what the frontend sends) → Qwen language names (what the model
# expects). Qwen3-ASR recognizes 30 languages.
ISO_TO_QWEN: Dict[str, str] = {
    "zh": "Chinese", "en": "English", "yue": "Cantonese", "ar": "Arabic",
    "de": "German", "fr": "French", "es": "Spanish", "pt": "Portuguese",
    "id": "Indonesian", "it": "Italian", "ko": "Korean", "ru": "Russian",
    "th": "Thai", "vi": "Vietnamese", "ja": "Japanese", "tr": "Turkish",
    "hi": "Hindi", "ms": "Malay", "nl": "Dutch", "sv": "Swedish",
    "da": "Danish", "fi": "Finnish", "pl": "Polish", "cs": "Czech",
    "fil": "Filipino", "fa": "Persian", "el": "Greek", "hu": "Hungarian",
    "mk": "Macedonian", "ro": "Romanian",
}
QWEN_TO_ISO: Dict[str, str] = {name: iso for iso, name in ISO_TO_QWEN.items()}

# Qwen3-ForcedAligner-0.6B supports word timestamp alignment for 11 languages.
ALIGNER_LANGUAGES = {
    "Chinese", "English", "Cantonese", "French", "German", "Italian",
    "Japanese", "Korean", "Portuguese", "Russian", "Spanish",
}

# ISO codes whose aligned tokens are glued without spaces.
CJK_ISO = {"zh", "ja", "ko", "th", "yue"}

_GLUE_PUNCT = ".,!?;:。，！？；：、…"


def join_aligned_tokens(tokens: List[str], iso: str) -> str:
    """Rebuilds readable text from aligner tokens. Latin tokens join with
    spaces, CJK/Thai tokens glue directly, punctuation always attaches to the
    previous token. Pure logic — unit-tested without models."""
    text = ""
    for tok in tokens:
        tok = (tok or "").strip()
        if not tok:
            continue
        if not text:
            text = tok
        elif tok[0] in _GLUE_PUNCT:
            text += tok
        else:
            text += ("" if iso in CJK_ISO else " ") + tok
    return text


class QwenTranscriptionService:
    """Same public interface as TranscriptionService."""

    def __init__(self, model: str = None):
        self.model = model or settings.QWEN_ASR_MODEL
        self.aligner_model = settings.QWEN_ASR_ALIGNER_MODEL
        self._backend = None
        self._client = None
        fix_cuda_paths()
        print(f"[Qwen-ASR] Initializing {self.model} (+ aligner {self.aligner_model})")
        self._load()

    # --- loading ----------------------------------------------------------
    def _import_backend(self):
        if self._backend is None:
            try:
                import torch
                from qwen_asr import Qwen3ASRModel
            except ImportError as e:
                raise RuntimeError(
                    "Qwen3-ASR is selected but the optional `qwen-asr` package is not "
                    f"installed. Install it with: pip install qwen-asr (reason: {e})"
                ) from e
            self._backend = (torch, Qwen3ASRModel)
        return self._backend

    def _load(self):
        torch, Qwen3ASRModel = self._import_backend()
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        print(f"[Qwen-ASR] Using device: {device}")
        try:
            self._client = Qwen3ASRModel.from_pretrained(
                self.model,
                dtype=dtype,
                device_map=device,
                max_inference_batch_size=settings.QWEN_ASR_MAX_BATCH,
                max_new_tokens=settings.QWEN_ASR_MAX_NEW_TOKENS,
                forced_aligner=self.aligner_model,
                forced_aligner_kwargs=dict(dtype=dtype, device_map=device),
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load Qwen3-ASR model: {e}") from e

    # --- language handling ------------------------------------------------
    @staticmethod
    def _normalize_language(language: str = None) -> Optional[str]:
        """Frontend ISO-639-1 code → Qwen English language name ('auto' → None
        for automatic detection). Raises a clear error for unsupported codes —
        transcribing in a language Qwen cannot hear must not fail silently."""
        if not language:
            return None
        language = language.lower().strip()
        if language == "auto":
            return None
        name = ISO_TO_QWEN.get(language)
        if name is None:
            raise RuntimeError(
                f"Qwen3-ASR does not support the language code '{language}'. "
                "Supported codes: " + ", ".join(sorted(ISO_TO_QWEN.keys()))
                + " — switch the transcription model to Whisper for other languages."
            )
        return name

    def _timestamps_compatible(self, language_name: Optional[str]) -> bool:
        """Word timestamps need an aligner-supported language (None = detected
        per window; a forced unsupported language disables them up front)."""
        return language_name is None or language_name in ALIGNER_LANGUAGES

    # --- core transcription ------------------------------------------------
    def _decode(self, audio_path: str):
        from faster_whisper.audio import decode_audio
        # decode_audio returns a single mono float32 ndarray at SRC rate
        audio = decode_audio(audio_path, sampling_rate=SAMPLE_RATE)
        return audio

    def _transcribe_windows(self, windows: List[Tuple[float, float]], audio: "np.ndarray",
                            language_name: Optional[str], context: str) -> List[Dict]:
        """Batch-transcribes speech windows; returns raw per-window results.
        Word timestamps are requested when the language is aligner-compatible;
        a backend refusal degrades to timing-free results (window bounds)."""
        page = max(1, settings.QWEN_ASR_MAX_BATCH)
        want_ts = self._timestamps_compatible(language_name)
        raw: List[Dict] = []
        for i in range(0, len(windows), page):
            batch = windows[i:i + page]
            audio_inputs = [(audio[int(s * SAMPLE_RATE):int(e * SAMPLE_RATE)], SAMPLE_RATE)
                            for s, e in batch]
            kwargs = dict(audio=audio_inputs,
                          language=[language_name] * len(batch),
                          context=[context] * len(batch))
            try:
                results = self._client.transcribe(return_time_stamps=want_ts, **kwargs)
            except (TypeError, ValueError, RuntimeError) as e:
                if not want_ts:
                    raise
                print(f"[Qwen-ASR] Timestamp pass failed ({e}) — retrying without word timing")
                results = self._client.transcribe(return_time_stamps=False, **kwargs)
            for w, r in zip(batch, results):
                raw.append({
                    "window": w,
                    "text": (getattr(r, "text", "") or "").strip(),
                    "language": getattr(r, "language", language_name),
                    "time_stamps": getattr(r, "time_stamps", None),
                })
        return raw

    def _raw_to_segments(self, raw: List[Dict], language_iso: Optional[str],
                         offset: float = 0.0) -> Tuple[List[Dict], Dict]:
        """Window results → subtitle segment dicts (Whisper dict shape)."""
        segments: List[Dict] = []
        n_word_timed = 0
        for r in raw:
            win_start, win_end = r["window"]
            tokens: List[Tuple[str, float, float]] = []
            if r["time_stamps"]:
                tokens = [(t.text, float(t.start_time) + win_start + offset,
                           float(t.end_time) + win_start + offset)
                          for t in r["time_stamps"]]
            iso = language_iso or QWEN_TO_ISO.get(r["language"] or "", "")
            if tokens:
                n_word_timed += 1
            elif (r["language"] or "") not in ALIGNER_LANGUAGES and r["text"]:
                print(f"[Qwen-ASR] Word timestamps unavailable for '{r['language']}' "
                      f"(aligner supports: {', '.join(sorted(ALIGNER_LANGUAGES))}) "
                      f"— using window boundary timing for {win_start + offset:.1f}s region")
            if tokens:
                segs = self._group_words(tokens, iso)
            elif r["text"]:
                segs = [{"start": win_start + offset, "end": win_end + offset,
                         "text": r["text"]}]
            else:
                segs = []
            for seg in segs:
                if (seg.get("text") or "").strip():
                    segments.append({"speaker": None, "avg_logprob": 0.0, **seg})
        segments.sort(key=lambda s: s["start"])
        return segments, {"windows": len(raw), "windows_word_timed": n_word_timed}

    @staticmethod
    def _group_words(words: List[Tuple[str, float, float]], iso: str) -> List[Dict]:
        """Groups aligned word timings into subtitle segment dicts.

        A new segment starts when the previous token ends a sentence
        (punctuation), the gap to the next token exceeds
        QWEN_SEGMENT_GAP_SECONDS, or the segment has run past
        QWEN_MAX_SEGMENT_SECONDS. Pure logic — unit-tested without models.
        """
        clean = [w for w in words if w[0] and w[0].strip()]
        if not clean:
            return []
        punct = ".,!?;:。，！？；：…"
        max_gap = settings.QWEN_SEGMENT_GAP_SECONDS
        max_dur = settings.QWEN_MAX_SEGMENT_SECONDS
        groups: List[List[Tuple[str, float, float]]] = []
        current: List[Tuple[str, float, float]] = []
        for w in clean:
            if not current:
                current.append(w)
                continue
            prev = current[-1]
            prev_ends_sentence = prev[0].strip().endswith(tuple(punct))
            gap = w[1] - prev[2]
            dur = w[2] - current[0][1]
            if prev_ends_sentence or gap > max_gap or dur > max_dur:
                groups.append(current)
                current = []
            current.append(w)
        if current:
            groups.append(current)
        return [{
            "start": g[0][1],
            "end": g[-1][2],
            "text": join_aligned_tokens([t for t, _, _ in g], iso),
            "words": [{"start": s, "end": e, "word": t.strip()} for t, s, e in g],
        } for g in groups]

    # --- public API (mirrors TranscriptionService) -------------------------
    def transcribe(self, audio_path: str, language: str = None,
                   initial_prompt: str = None, hotwords: str = None):
        language_name = self._normalize_language(language)
        print(f"[Qwen-ASR] Starting transcription for {os.path.basename(audio_path)}")
        try:
            audio = self._decode(audio_path)
        except Exception as e:
            raise RuntimeError(f"Could not decode audio '{audio_path}': {e}")
        duration = len(audio) / SAMPLE_RATE
        windows = vad.speech_windows(audio)
        if not windows:
            print("[Qwen-ASR] No speech detected in the audio — nothing to transcribe")
            return [], {"windows": 0, "windows_word_timed": 0,
                        "silence_skipped_seconds": round(duration, 2),
                        "dropped": [], "retry_regions": 0}

        total_speech = sum(e - s for s, e in windows)
        silence_skipped = max(0.0, duration - total_speech)
        print(f"[Qwen-ASR] {len(windows)} speech window(s), "
              f"{silence_skipped:.1f}s of silence skipped")

        context = " ".join(t.strip() for t in [initial_prompt or "", hotwords or ""] if t.strip())
        raw = self._transcribe_windows(windows, audio, language_name, context)
        segments, meta = self._raw_to_segments(raw, language_iso=None)
        meta.update({"silence_skipped_seconds": round(silence_skipped, 2),
                     "dropped": [], "retry_regions": 0})
        print(f"[Qwen-ASR] Transcription complete. Found {len(segments)} segments "
              f"({meta['windows_word_timed']}/{meta['windows']} word-timed).")
        return segments, meta

    def transcribe_segment(self, audio_path: str, chunk_start_offset: float,
                           language: str = None) -> List[Dict]:
        """Transcribes a live audio chunk with timestamps offset to absolute
        video time. A fully silent chunk returns [] without any model call."""
        language_name = self._normalize_language(language)
        try:
            audio = self._decode(audio_path)
        except Exception as e:
            raise RuntimeError(f"Could not decode audio chunk '{audio_path}': {e}")
        windows = vad.speech_windows(audio)
        if not windows:
            print(f"[Qwen-ASR] Chunk at {chunk_start_offset:.0f}s: no speech detected (skipped)")
            return []
        raw = self._transcribe_windows(windows, audio, language_name, context="")
        segments, _ = self._raw_to_segments(raw, language_iso=None,
                                            offset=chunk_start_offset)
        print(f"[Qwen-ASR] Chunk starting at {chunk_start_offset}s: found {len(segments)} segments")
        return segments

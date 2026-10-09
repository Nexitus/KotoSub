from typing import List, Dict, Any
import os
from app.cuda import fix_cuda_paths
from app.config import settings

try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    torch = None
    _TORCH_AVAILABLE = False

def select_transcription_class(model: str = None) -> type:
    """Engine routing: Whisper is the default; any Qwen3-ASR model id routes to
    the Qwen engine. Pure selection (no instantiation) so it stays unit-testable."""
    name = (model or settings.LOCAL_WHISPER_MODEL).lower()
    if "qwen3-asr" in name:
        from app.processors.qwen_asr import QwenTranscriptionService
        return QwenTranscriptionService
    return TranscriptionService

def create_transcription_service(model: str = None, **kwargs):
    """Builds the transcription service for the requested model."""
    return select_transcription_class(model)(model=model, **kwargs)

class TranscriptionService:
    def __init__(self, model: str = None):
        self.model = model or settings.LOCAL_WHISPER_MODEL
        fix_cuda_paths()
        print(f"[Transcription] Initializing Local Whisper Model: {self.model}")
        from faster_whisper import WhisperModel
        device = "cuda" if (_TORCH_AVAILABLE and torch.cuda.is_available()) else "cpu"
        print(f"[Transcription] Using device: {device}")
        compute_type = "float16" if device == "cuda" else "int8"
        try:
            self.local_client = WhisperModel(
                self.model,
                device=device,
                compute_type=compute_type,
                download_root=settings.MODELS_DIR
            )
        except Exception as e:
            print(f"[Transcription] Error loading local model: {e}")
            raise RuntimeError(f"Failed to load local Whisper model: {e}")

    @staticmethod
    def _normalize_language(language: str = None):
        """'auto'/'Auto' → None (let Whisper detect); otherwise pass through.
        The frontend sends ISO-639-1 codes."""
        if not language:
            return None
        language = language.lower().strip()
        return None if language == 'auto' else language

    def _whisper_kwargs(self, language: str = None, beam_size: int = None,
                        clip_timestamps: List[float] = None,
                        initial_prompt: str = None, hotwords: str = None,
                        anneal: bool = False) -> Dict[str, Any]:
        """Shared transcription parameters (refinement: word timestamps +
        hallucination controls configurable via .env). `anneal=True` adds the
        retry-pass temperature ladder + patience that rescue segment looping
        on noisy audio; pass-1 decode is untouched."""
        kwargs = {
            "language": language,
            "beam_size": beam_size or 5,
            "word_timestamps": settings.WHISPER_WORD_TIMESTAMPS,
            "condition_on_previous_text": settings.WHISPER_CONDITION_ON_PREVIOUS_TEXT,
            "no_speech_threshold": settings.WHISPER_NO_SPEECH_THRESHOLD,
            "log_prob_threshold": settings.WHISPER_LOG_PROB_THRESHOLD,
            "compression_ratio_threshold": settings.WHISPER_COMPRESSION_RATIO_THRESHOLD,
            "vad_filter": True,
            "vad_parameters": dict(min_silence_duration_ms=500,
                                   speech_pad_ms=settings.WHISPER_SPEECH_PAD_MS)
        }
        if anneal:
            temps = [t.strip() for t in settings.WHISPER_RETRY_TEMPERATURE.split(",") if t.strip()]
            kwargs["temperature"] = temps
            kwargs["patience"] = settings.WHISPER_RETRY_PATIENCE
        if clip_timestamps:
            kwargs["clip_timestamps"] = clip_timestamps
        if initial_prompt:
            kwargs["initial_prompt"] = initial_prompt
        if hotwords:
            kwargs["hotwords"] = hotwords
        return kwargs

    @staticmethod
    def _extract_words(segment) -> List[Dict[str, Any]]:
        """Extracts word-level timings from a faster-whisper segment, if present."""
        words = getattr(segment, "words", None)
        if not words:
            return []
        return [{"start": w.start, "end": w.end, "word": w.word.strip()} for w in words]

    @staticmethod
    def _is_hallucination(text: str, no_speech_prob: float) -> bool:
        """VAD said 'no speech' but Whisper still emitted a short boilerplate
        string (music/silence hallucinations like 'Thank you.')."""
        return (no_speech_prob > settings.WHISPER_NO_SPEECH_DROP_PROB
                and len(text) <= settings.WHISPER_HALLUCINATION_MAX_CHARS)

    @staticmethod
    def _is_repetition_loop(prev_text: str, text: str) -> bool:
        """Detects the classic noisy-audio ASR failure: the same token 3-grams
        repeating across consecutive segments or inside one segment
        (e.g. 'Order. Order. All in favor say ... Order. Order.').
        Runs BEFORE any LLM sees the text — loop regions are re-transcribed,
        never repaired (docs/TRANSCRIPTION_PIPELINE.md)."""
        import re as _re
        def tokenize(t: str):
            # Keep apostrophes inside words (that's -> thats); apostrophe as a
            # token separator would hallucinate duplicate 3-grams in normal
            # emphatic speech ("that's right, that's right").
            t = t.lower().replace("'", "").replace("\u2019", "")
            return _re.sub(r"[^\w\s]", " ", t).split()
        a, b = tokenize(prev_text), tokenize(text)
        # Intra-segment loop: same 3-gram appearing twice (needs enough tokens
        # to house two distinct 3-grams with meaning)
        b_trigrams = [tuple(b[i:i + 3]) for i in range(len(b) - 2)]
        if len(b) >= 5 and len(b_trigrams) != len(set(b_trigrams)):
            return True
        # Short segments overlap trivially; inter-segment loops need depth
        if len(a) < 4 or len(b) < 4:
            return False
        # Inter-segment loop: heavy 3-gram overlap with the previous segment
        tg_a = set(tuple(a[i:i + 3]) for i in range(len(a) - 2))
        tg_b = set(b_trigrams)
        union = tg_a | tg_b
        if not union:
            return False
        return len(tg_a & tg_b) / len(union) >= settings.WHISPER_LOOP_OVERLAP_THRESHOLD

    @staticmethod
    def _segment_to_dict(segment, index_offset: float = 0.0) -> Dict[str, Any]:
        d = {
            "start": segment.start + index_offset,
            "end": segment.end + index_offset,
            "text": segment.text.strip(),
            "speaker": None,
            "avg_logprob": segment.avg_logprob,
        }
        words = TranscriptionService._extract_words(segment)
        if words:
            for w in words:
                w["start"] += index_offset
                w["end"] += index_offset
            d["words"] = words
        return d

    def transcribe(self, audio_path: str, language: str = None,
                   initial_prompt: str = None, hotwords: str = None) -> List[Dict[str, Any]]:
        language = self._normalize_language(language)

        print(f"[Transcription] Starting local transcription for {os.path.basename(audio_path)}")
        try:
            segments, info = self.local_client.transcribe(
                audio_path,
                **self._whisper_kwargs(language, initial_prompt=initial_prompt, hotwords=hotwords)
            )
            print(f"[Transcription] Detected language: {info.language} with probability {info.language_probability}")
            all_segments = []
            retry_regions = []
            dropped = []
            prev_text = ""
            for i, segment in enumerate(segments):
                idx = i + 1
                if idx % 10 == 0:
                    print(f"[Whisper] processed {idx} segments...")
                text = segment.text.strip()
                if self._is_hallucination(text, segment.no_speech_prob):
                    dropped.append({"start": segment.start, "end": segment.end,
                                    "text": text,
                                    "no_speech_prob": segment.no_speech_prob})
                    continue
                seg_dict = self._segment_to_dict(segment)
                # Audit: low confidence OR repetition loop OR the segment's own
                # compression ratio already over threshold → retry the region
                # at a wider beam instead of letting garbage reach the LLM.
                loop = (self._is_repetition_loop(prev_text, text)
                        or segment.compression_ratio > settings.WHISPER_COMPRESSION_RATIO_THRESHOLD)
                if loop or seg_dict["avg_logprob"] < settings.WHISPER_RETRY_LOGPROB:
                    seg_dict["_flagged"] = True
                    retry_regions.append((seg_dict["start"], seg_dict["end"]))
                prev_text = text
                all_segments.append(seg_dict)
            if dropped:
                examples = ", ".join(f"@{d['start']:.1f}s" for d in dropped[:5])
                print(f"[Transcription] Dropped {len(dropped)} suspected hallucinated segment(s) "
                      f"(verify against the source if subtitles seem incomplete): {examples}")
            print(f"[Transcription] Local transcription complete. Found {len(all_segments)} segments"
                  + (f", dropped {len(dropped)} hallucinated" if dropped else "") + ".")

            # Two-tier pass: re-transcribe flagged regions (low confidence or
            # repetition loops) with a wider beam + temperature ladder.
            if retry_regions:
                print(f"[Transcription] Re-transcribing {len(retry_regions)} flagged region(s) "
                      f"with beam_size={settings.WHISPER_RETRY_BEAM_SIZE}...")
                clips = [t for region in retry_regions for t in region]
                retry_kwargs = self._whisper_kwargs(language, beam_size=settings.WHISPER_RETRY_BEAM_SIZE,
                                                    clip_timestamps=clips,
                                                    initial_prompt=initial_prompt, hotwords=hotwords,
                                                    anneal=True)
                try:
                    retry_segments, _ = self.local_client.transcribe(
                        audio_path,
                        **retry_kwargs
                    )
                    retry_out = [self._segment_to_dict(s) for s in retry_segments]
                    print(f"[Transcription] Retry pass produced {len(retry_out)} segments.")
                    all_segments = ([s for s in all_segments if not s.get("_flagged")]
                                    + retry_out)
                    all_segments.sort(key=lambda s: s["start"])
                except TypeError:
                    print("[Transcription] Installed faster-whisper does not support "
                          "clip_timestamps/annealing kwargs — keeping original segments.")
            meta = {"dropped": dropped, "retry_regions": len(retry_regions)}
            return all_segments, meta
        except Exception as e:
            print(f"[Transcription] Local transcription error: {e}")
            raise e

    def transcribe_segment(self, audio_path: str, chunk_start_offset: float,
                           language: str = None) -> List[Dict[str, Any]]:
        """Transcribe a single audio chunk file. Timestamps are offset to
        absolute video time by adding chunk_start_offset to each segment's
        start/end.
        Returns: [{"start": abs_start, "end": abs_end, "text": "...", "speaker": None}]
        """
        language = self._normalize_language(language)

        try:
            segments, info = self.local_client.transcribe(
                audio_path,
                **self._whisper_kwargs(language)
            )
            all_segments = []
            for segment in segments:
                if self._is_hallucination(segment.text.strip(), segment.no_speech_prob):
                    continue
                all_segments.append(self._segment_to_dict(segment, index_offset=chunk_start_offset))
            print(f"[Whisper] Chunk starting at {chunk_start_offset}s: found {len(all_segments)} segments")
            return all_segments
        except Exception as e:
            print(f"[Transcription] Chunk transcription error: {e}")
            raise e

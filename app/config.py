from typing import Optional
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # App Settings
    TEMP_DIR: str = os.path.join(os.getcwd(), "temp")
    OUTPUT_DIR: str = os.path.join(os.getcwd(), "output")
    MODELS_DIR: str = os.path.join(os.getcwd(), "models")

    # HuggingFace token for diarization and model downloads
    HF_TOKEN: Optional[str] = None

    # Local Whisper Settings
    # Options: tiny, base, small, medium, large-v3, large-v3-turbo, distil-whisper/distil-large-v3.5-ct2
    LOCAL_WHISPER_MODEL: str = "large-v3-turbo"

    # Audio extraction: aggressive denoise often hurts Whisper (it was trained
    # on noisy audio). Loudnorm + highpass always run; afftdn is opt-in or
    # auto-triggered by a cheap ffmpeg noise-floor probe in video.py.
    # Values: auto (probe decides) | on (always denoise) | off (never).
    AUDIO_ENHANCE: str = "auto"
    # Probe threshold: noise floor (dBFS, louder = higher) above which the
    # auto preset applies the denoise/compression filter chain.
    AUDIO_PROBE_NOISE_FLOOR_DB: float = -45.0

    # Whisper refinement: word-level timestamps + hallucination controls
    WHISPER_WORD_TIMESTAMPS: bool = True
    WHISPER_CONDITION_ON_PREVIOUS_TEXT: bool = False
    WHISPER_NO_SPEECH_THRESHOLD: float = 0.6
    WHISPER_LOG_PROB_THRESHOLD: float = -1.0
    WHISPER_COMPRESSION_RATIO_THRESHOLD: float = 2.4
    # Pad VAD speech regions so word onsets aren't clipped
    WHISPER_SPEECH_PAD_MS: int = 100
    # Hallucination sweep: drop segments flagged as non-speech that whisper
    # filled with boilerplate ("Thank you.", "Bye.", etc.)
    WHISPER_NO_SPEECH_DROP_PROB: float = 0.9
    WHISPER_HALLUCINATION_MAX_CHARS: int = 32
    # Two-tier retry: re-transcribe low-confidence regions with a wider beam
    WHISPER_RETRY_LOGPROB: float = -0.8
    WHISPER_RETRY_BEAM_SIZE: int = 10
    # Retry pass annealing: temperature ladder + patience rescue segment
    # looping on noisy audio (pass 1 decode is untouched).
    WHISPER_RETRY_TEMPERATURE: str = "0.0,0.2,0.4,0.6,0.8,1.0"
    WHISPER_RETRY_PATIENCE: float = 2.0
    # Audit: token 3-gram overlap fraction across consecutive segments above
    # which the region is flagged as a repetition loop and retried.
    WHISPER_LOOP_OVERLAP_THRESHOLD: float = 0.6

    # Alternative transcription engine: Qwen3-ASR (via the `qwen-asr` package,
    # optional dependency). Whisper remains the default; select the Qwen engine
    # by passing its model id through the frontend transcription selector.
    QWEN_ASR_MODEL: str = "Qwen/Qwen3-ASR-1.7B"
    QWEN_ASR_ALIGNER_MODEL: str = "Qwen/Qwen3-ForcedAligner-0.6B"
    QWEN_ASR_MAX_NEW_TOKENS: int = 256
    QWEN_ASR_MAX_BATCH: int = 8
    # Speech windows longer than this are re-split at silence gaps — keeps the
    # forced aligner (≤5 min) and decoder prompt comfortably small.
    QWEN_MAX_WINDOW_SECONDS: float = 28.0
    # Word-level timing grouping: a gap longer than this between two aligned
    # words starts a new subtitle segment; segments never exceed the max length.
    QWEN_SEGMENT_GAP_SECONDS: float = 0.8
    QWEN_MAX_SEGMENT_SECONDS: float = 6.0

    # Silence detection (Silero VAD, faster-whisper's model). Runs before the
    # Qwen engine (speech windows + skip silent chunks in live) so silence is
    # never sent to a model. Whisper applies its own VAD internally.
    VAD_MIN_SPEECH_MS: int = 250
    VAD_MIN_SILENCE_MS: int = 500
    VAD_SPEECH_PAD_MS: int = 200

    # Local LLM Settings
    # Default: Translate Gemma 4 Sub E4B — subtitle-specialized, fits comfortably
    # in 16 GB VRAM. For Japanese sources the recommended model is Sugoi 32B
    # Ultra (see download_models.RECOMMENDED_BY_LANG / /api/models).
    LOCAL_LLM_MODEL: str = "17slever17/translate-gemma-4-sub-e4b-GGUF"
    LOCAL_LLM_FILE: Optional[str] = "translate_gemma4_sub-E4B-Q4_K_XL.gguf"

    LLM_FREQUENCY_PENALTY: float = 0.1
    LLM_PRESENCE_PENALTY: float = 0.1

    # Contextual batch translation
    LLM_N_CTX: int = 4096
    LLM_TRANSLATE_BATCH: int = 12
    LLM_CONTEXT_LINES: int = 12
    LLM_TRANSLATE_TEMPERATURE: float = 0.15

    # Quality check: only re-verify suspect segments. When COMETKiwi is
    # installed, segments scoring below this threshold are also re-checked.
    QA_USE_COMET: bool = True
    QA_COMET_THRESHOLD: float = 0.65

    # Subtitle refinement: characters-per-second limits.
    # CJK subtitles are character-dense, so they use a stricter limit.
    SUBTITLE_MAX_CPS: int = 20
    SUBTITLE_MAX_CPS_CJK: int = 11
    # Never produce split subtitles shorter than this (seconds)
    SUBTITLE_MIN_SPLIT_SECONDS: float = 1.0
    # Timing polish: lead-in before first word, linger after last word
    SUBTITLE_LEAD_IN_SECONDS: float = 0.12
    SUBTITLE_TRAIL_SECONDS: float = 0.35

    # RTX 5070 Ti / Blackwell optimizations
    LLM_N_BATCH: int = 1024
    LLM_N_THREADS: int = 4
    LLM_FLASH_ATTN: bool = True
    GPU_CODEC_CHAIN: str = "hevc_nvenc,av1_nvenc,h264_nvenc"
    LIVE_LOOKAHEAD_SECONDS: int = 30
    LIVE_CHUNK_OVERLAP_SECONDS: float = 1.5
    LIVE_FALLBACK_LLM_MODEL: str = "unsloth/Qwen3.5-9B-GGUF"
    LIVE_FALLBACK_LLM_FILE: str = "Qwen3.5-9B-Q4_K_M.gguf"
    LIVE_SESSION_TIMEOUT_SECONDS: int = 120
    LIVE_REMUX_DIR: str = os.path.join(os.getcwd(), "temp", "remux")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()

# Ensure directories exist
os.makedirs(settings.TEMP_DIR, exist_ok=True)
os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
os.makedirs(settings.MODELS_DIR, exist_ok=True)
os.makedirs(settings.LIVE_REMUX_DIR, exist_ok=True)

"""Shared silence detection (Silero VAD).

Audio detection scope: speech regions are found BEFORE any transcription
engine is invoked so silence is never decoded. Whisper applies its own
internal VAD; this module is used by the Qwen3-ASR engine (speech windows)
and by the live pipeline (skip whole silent chunks).

The VAD model itself is Silero, vendored with faster-whisper which is
already installed — no new dependency.
"""
from typing import List, Optional, Tuple

import numpy as np

from app.config import settings

try:
    from faster_whisper.audio import decode_audio
    from faster_whisper.vad import VadOptions, get_speech_timestamps
    _VAD_AVAILABLE = True
except ImportError:
    _VAD_AVAILABLE = False

SAMPLE_RATE = 16000


def get_speech_regions(audio_path: str) -> Optional[List[Tuple[float, float]]]:
    """Returns speech regions as absolute time ranges [(start, end), ...].

    Regions longer than QWEN_MAX_WINDOW_SECONDS are split by the VAD itself at
    internal stop gaps (~100 ms), so window grouping never cuts speech.

    None means the VAD is unavailable or failed (feature off — treat the whole
    track as speech, behavior unchanged). An empty list means genuinely silent.
    """
    if not _VAD_AVAILABLE:
        return None
    try:
        audio = decode_audio(audio_path, sampling_rate=SAMPLE_RATE)
        return [(t["start"] / SAMPLE_RATE, t["end"] / SAMPLE_RATE)
                for t in _timestamps(audio)]
    except Exception as e:
        print(f"[VAD] Silence detection failed ({e}) — treating all audio as speech")
        return None


def _timestamps(audio: np.ndarray) -> List[dict]:
    options = VadOptions(
        min_speech_duration_ms=settings.VAD_MIN_SPEECH_MS,
        min_silence_duration_ms=settings.VAD_MIN_SILENCE_MS,
        speech_pad_ms=settings.VAD_SPEECH_PAD_MS,
        max_speech_duration_s=settings.QWEN_MAX_WINDOW_SECONDS,
    )
    return get_speech_timestamps(audio, options, sampling_rate=SAMPLE_RATE)


def speech_windows(audio: np.ndarray) -> List[Tuple[float, float]]:
    """Runs the VAD on decoded 16 kHz audio and groups the resulting speech
    regions into bounded transcription windows.

    Degrades on any VAD failure: the whole track becomes one window so the
    engine keeps working (same behavior as before silence detection existed).
    A clean empty result means genuinely silent audio — caller skips it.
    """
    if not _VAD_AVAILABLE:
        return [(0.0, len(audio) / SAMPLE_RATE)]
    try:
        regions = [(t["start"] / SAMPLE_RATE, t["end"] / SAMPLE_RATE)
                   for t in _timestamps(audio)]
    except Exception as e:
        print(f"[VAD] Silence detection failed ({e}) — transcribing the whole track")
        return [(0.0, len(audio) / SAMPLE_RATE)]
    return windows_from_regions(regions, settings.QWEN_MAX_WINDOW_SECONDS)


def windows_from_regions(speech_regions: List[Tuple[float, float]],
                         max_window_s: float) -> List[Tuple[float, float]]:
    """Groups pre-split speech regions into bounded transcription windows.

    Greedy: a region extends the current window only while the span stays
    within `max_window_s`. The VAD already splits long speech at internal
    silence, so span overflow here is the only remaining cap.

    Pure logic — unit-testable without the VAD model.
    """
    windows: List[List[float]] = []
    for r_start, r_end in speech_regions:
        if windows and r_end - windows[-1][0] <= max_window_s:
            windows[-1][1] = max(windows[-1][1], r_end)
        else:
            windows.append([r_start, r_end])
    return [(w[0], w[1]) for w in windows]


def has_speech(audio_path: str) -> bool:
    """True unless the VAD ran and found zero speech regions."""
    regions = get_speech_regions(audio_path)
    return regions is None or bool(regions)

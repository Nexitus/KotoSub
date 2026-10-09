"""Unit tests for the Qwen3-ASR engine, engine routing, and silence windows.

Run: python -m pytest tests/test_qwen_asr.py
No model downloads and no torch inference: pure logic (language routing,
word grouping, token joining, window bounds/offsets, silence skip) is
covered with fakes.
"""
import unittest
from unittest import mock

from app.config import settings
from app.processors import vad


def _make_service(**overrides):
    """Builds QwenTranscriptionService without loading a real model."""
    from app.processors.qwen_asr import QwenTranscriptionService
    svc = QwenTranscriptionService.__new__(QwenTranscriptionService)
    svc.model = settings.QWEN_ASR_MODEL
    svc.aligner_model = settings.QWEN_ASR_ALIGNER_MODEL
    svc._backend = object()
    svc._client = None
    for k, v in overrides.items():
        setattr(svc, k, v)
    return svc


class _FakeResult:
    def __init__(self, text, language, time_stamps):
        self.text = text
        self.language = language
        self.time_stamps = time_stamps


class TestEngineRouting(unittest.TestCase):
    """Transcription selector: Whisper is the default; Qwen3-ASR ids route to
    the Qwen engine."""

    def test_whisper_is_default(self):
        from app.processors.transcription import TranscriptionService, select_transcription_class
        self.assertIs(select_transcription_class(None), TranscriptionService)
        self.assertIs(select_transcription_class(""), TranscriptionService)
        self.assertIs(select_transcription_class("large-v3-turbo"), TranscriptionService)
        self.assertIs(
            select_transcription_class("distil-whisper/distil-large-v3.5-ct2"),
            TranscriptionService)

    def test_qwen_id_routes_to_qwen_engine(self):
        from app.processors.transcription import select_transcription_class
        from app.processors.qwen_asr import QwenTranscriptionService
        self.assertIs(select_transcription_class("Qwen/Qwen3-ASR-1.7B"),
                      QwenTranscriptionService)


class TestLanguageMapping(unittest.TestCase):
    def test_iso_to_qwen_names(self):
        from app.processors.qwen_asr import QwenTranscriptionService as S
        self.assertEqual(S._normalize_language(None), None)
        self.assertEqual(S._normalize_language("auto"), None)
        self.assertEqual(S._normalize_language("AUTO"), None)
        self.assertEqual(S._normalize_language("ja"), "Japanese")
        self.assertEqual(S._normalize_language("en"), "English")
        self.assertEqual(S._normalize_language("zh"), "Chinese")

    def test_unsupported_language_fails_loudly(self):
        from app.processors.qwen_asr import QwenTranscriptionService as S
        for iso in ("uk", "bg", "hr", "sr", "no", "sk", "xx"):
            with self.assertRaises(RuntimeError) as ctx:
                S._normalize_language(iso)
            msg = str(ctx.exception)
            self.assertIn(iso, msg)
            self.assertIn("Qwen3-ASR does not support", msg)
            self.assertIn("Whisper", msg)


class TestTimestampCompatibility(unittest.TestCase):
    def test_forced_unsupported_language_disables_timestamps(self):
        svc = _make_service()
        self.assertTrue(svc._timestamps_compatible(None))        # auto-detect
        self.assertTrue(svc._timestamps_compatible("Japanese"))  # aligner supports
        self.assertFalse(svc._timestamps_compatible("Thai"))     # not in aligner list


class TestTokenJoining(unittest.TestCase):
    def test_latin_joins_with_spaces(self):
        from app.processors.qwen_asr import join_aligned_tokens
        self.assertEqual(
            join_aligned_tokens(["Hello", "world", "again"], "en"),
            "Hello world again")

    def test_punctuation_glues_to_previous_token(self):
        from app.processors.qwen_asr import join_aligned_tokens
        self.assertEqual(
            join_aligned_tokens(["Hello", "world", ",", "again"], "en"),
            "Hello world, again")

    def test_cjk_glues_without_spaces(self):
        from app.processors.qwen_asr import join_aligned_tokens
        self.assertEqual(
            join_aligned_tokens(["今", "日", "は", "晴", "れ", "。"], "ja"),
            "今日は晴れ。")
        self.assertEqual(
            join_aligned_tokens(["交易", "几乎", "停滞", "。"], "zh"),
            "交易几乎停滞。")


class TestWordGrouping(unittest.TestCase):
    def _svc(self):
        return _make_service()

    def test_plain_words_form_one_segment(self):
        words = [("Hello", 0.0, 0.3), ("world", 0.4, 0.7)]
        segs = self._svc()._group_words(words, "en")
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0]["start"], 0.0)
        self.assertEqual(segs[0]["end"], 0.7)
        self.assertEqual(segs[0]["text"], "Hello world")
        self.assertEqual(segs[0]["words"][0]["word"], "Hello")

    def test_gap_starts_new_segment(self):
        gap = settings.QWEN_SEGMENT_GAP_SECONDS
        words = [("Hello", 0.0, 0.3),
                 ("world", 0.3 + gap + 0.1, 0.3 + gap + 0.3)]
        segs = self._svc()._group_words(words, "en")
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0]["end"], 0.3)
        self.assertEqual(segs[1]["start"], 0.3 + gap + 0.1)

    def test_sentence_punctuation_starts_new_segment(self):
        words = [("Okay", 0.0, 0.3), (".", 0.35, 0.35), ("Next", 0.5, 0.9)]
        segs = self._svc()._group_words(words, "en")
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[0]["text"], "Okay.")

    def test_max_duration_starts_new_segment(self):
        # words every 0.1s across a long span; no gaps, no punctuation
        words = [(f"w{i}", i * 0.1, i * 0.1 + 0.08) for i in range(200)]
        segs = self._svc()._group_words(words, "en")
        self.assertGreater(len(segs), 1)
        for seg in segs:
            overshoot = seg["end"] - seg["start"] - settings.QWEN_MAX_SEGMENT_SECONDS
            # a group only overflows the cap by up to one token's duration
            self.assertLessEqual(overshoot, 0.2)

    def test_empty_tokens_return_no_segments(self):
        self.assertEqual(self._svc()._group_words([], "en"), [])


class TestRawToSegments(unittest.TestCase):
    def test_window_offset_applied_to_word_timestamps(self):
        svc = _make_service()
        ts = [mock.Mock(text="Hello", start_time=0.1, end_time=0.4),
              mock.Mock(text="world", start_time=0.5, end_time=0.8)]
        raw = [{"window": (10.0, 12.0), "text": "Hello world",
                "language": "English", "time_stamps": ts}]
        segments, meta = svc._raw_to_segments(raw, None, offset=300.0)
        self.assertEqual(meta["windows"], 1)
        self.assertEqual(meta["windows_word_timed"], 1)
        self.assertEqual(len(segments), 1)
        self.assertAlmostEqual(segments[0]["start"], 310.1)
        self.assertAlmostEqual(segments[0]["end"], 310.8)
        self.assertEqual(segments[0]["speaker"], None)
        self.assertEqual(segments[0]["words"][0]["start"], 310.1)

    def test_no_timestamps_uses_window_bounds(self):
        svc = _make_service()
        raw = [{"window": (5.0, 8.0), "text": "Some speech",
                "language": "Thai", "time_stamps": None}]
        segments, meta = svc._raw_to_segments(raw, None)
        self.assertEqual(meta["windows_word_timed"], 0)
        self.assertEqual(segments[0]["start"], 5.0)
        self.assertEqual(segments[0]["end"], 8.0)
        self.assertEqual(segments[0]["text"], "Some speech")

    def test_unsupported_aligner_language_prints_clear_message(self):
        svc = _make_service()
        raw = [{"window": (0.0, 2.0), "text": "text",
                "language": "Ukrainian", "time_stamps": None}]
        with mock.patch("builtins.print") as p:
            svc._raw_to_segments(raw, None)
        printed = " ".join(str(c) for c in p.call_args_list)
        self.assertIn("Word timestamps unavailable", printed)
        self.assertIn("Ukrainian", printed)

    def test_empty_windows_produce_no_segments(self):
        svc = _make_service()
        raw = [{"window": (0.0, 2.0), "text": "", "language": "English",
                "time_stamps": None}]
        segments, _meta = svc._raw_to_segments(raw, None)
        self.assertEqual(segments, [])  # a window the model heard nothing in


class TestSilenceWindows(unittest.TestCase):
    """Audio detection: silence is grouped away, windows never exceed the cap."""

    def test_greedy_grouping_bounded(self):
        regions = [(0.0, 2.0), (3.0, 5.0), (6.0, 8.0)]
        windows = vad.windows_from_regions(regions, max_window_s=6.0)
        # (0-2)+(3-5) spans 5 s <= 6 → one window; (6-8) would span 8 > 6 → split
        self.assertEqual(windows, [(0.0, 5.0), (6.0, 8.0)])

    def test_all_speech_covered_long_track(self):
        regions = [(i * 3.0, i * 3.0 + 2.0) for i in range(200)]  # 10 min track
        windows = vad.windows_from_regions(regions, max_window_s=settings.QWEN_MAX_WINDOW_SECONDS)
        self.assertEqual(windows[0][0], 0.0)
        self.assertEqual(windows[-1][1], 199 * 3.0 + 2.0)
        for start, end in windows:
            self.assertLessEqual(end - start, settings.QWEN_MAX_WINDOW_SECONDS)

    def test_overlapping_long_region_never_lost(self):
        windows = vad.windows_from_regions([(0.0, 60.0)], max_window_s=28.0)
        # VAD pre-split long speech; a single overlong region is still kept
        self.assertEqual(windows, [(0.0, 60.0)])


class TestSilentChunkSkip(unittest.TestCase):
    """Silence must return [] without any model call."""

    def test_silent_chunk_short_circuits(self):
        svc = _make_service()
        audio = object()  # sentinel; _decode must return before use matters
        with mock.patch.object(type(svc), "_decode", return_value=audio), \
             mock.patch.object(vad, "speech_windows", return_value=[]):
            svc._client = mock.Mock()
            result = svc.transcribe_segment("fake.wav", chunk_start_offset=12.0, language="en")
        self.assertEqual(result, [])
        self.assertEqual(svc._client.transcribe.call_count, 0)

    def test_silent_full_track_returns_empty_with_meta(self):
        svc = _make_service()
        audio = mock.MagicMock()
        audio.__len__.return_value = int(30.0 * vad.SAMPLE_RATE)
        with mock.patch.object(type(svc), "_decode", return_value=audio), \
             mock.patch.object(vad, "speech_windows", return_value=[]):
            segments, meta = svc.transcribe("fake.wav", language=None)
        self.assertEqual(segments, [])
        self.assertEqual(meta["windows"], 0)
        self.assertEqual(meta["silence_skipped_seconds"], 30.0)


class TestBatchTimestampFallback(unittest.TestCase):
    """Aligner refusal degrades to a no-timestamp pass instead of crashing."""

    def test_retry_without_timestamps_on_error(self):
        svc = _make_service()
        windows = [(0.0, 28.0), (28.0, 56.0)]
        calls = []

        def fake_transcribe(return_time_stamps, **kwargs):
            calls.append(return_time_stamps)
            if return_time_stamps:
                raise RuntimeError("alignment not supported for language")
            audio_inputs = kwargs.get("audio") or []
            return [_FakeResult(text="hello", language="English", time_stamps=None)
                    for _ in audio_inputs]

        fake_client = mock.Mock()
        fake_client.transcribe.side_effect = fake_transcribe
        svc._client = fake_client
        audio = mock.MagicMock()
        audio.__len__.return_value = int(56.0 * vad.SAMPLE_RATE)
        raw = svc._transcribe_windows(windows, audio, "English", context="")
        self.assertEqual(calls, [True, False])  # timestamps pass refused, retry plain
        self.assertEqual(len(raw), 2)
        self.assertTrue(all(r["time_stamps"] is None for r in raw))
        self.assertEqual(svc._client.transcribe.call_count, 2)


class TestWorkerRouting(unittest.TestCase):
    """The live worker must route through the factory so live sessions support
    both engines with the same protocol."""

    def test_worker_uses_factory(self):
        import inspect
        import app.processors.whisper_worker as worker
        src = inspect.getsource(worker)
        self.assertIn("create_transcription_service", src)
        self.assertNotIn("TranscriptionService(model=", src)


class TestDownloadStatus(unittest.TestCase):
    """Model manager status helpers stay offline-safe."""

    def test_no_cache_dir_means_missing(self):
        import download_models
        with mock.patch.object(download_models, "_hf_cache_dir",
                               side_effect=RuntimeError("no cache")):
            self.assertFalse(download_models.qwen_asr_installed())

    def test_both_repo_snapshots_mean_installed(self):
        import download_models
        with mock.patch.object(download_models, "_hf_cache_dir", return_value="/cache"), \
             mock.patch("os.path.isdir", return_value=True), \
             mock.patch("os.scandir", side_effect=lambda p: iter([object()])):
            self.assertTrue(download_models.qwen_asr_installed())

    def test_single_repo_only_means_missing(self):
        """Half a download (ASR without the aligner) must not read as ready."""
        import download_models
        import os
        def fake_isdir(path):
            if os.path.basename(path) != "snapshots":
                return False
            return "Qwen3-ASR-" in path and "ForcedAligner" not in path
        with mock.patch.object(download_models, "_hf_cache_dir", return_value="/cache"), \
             mock.patch("os.path.isdir", side_effect=fake_isdir):
            self.assertFalse(download_models.qwen_asr_installed())


if __name__ == "__main__":
    unittest.main()

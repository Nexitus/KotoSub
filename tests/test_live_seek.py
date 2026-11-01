"""Live covered-footage intervals and seek behavior (audit item 8).

Coverage is a set of merged intervals, so a forward seek leaves a hole and a
later rewind into that hole restarts extraction at the playhead instead of
waiting forever on a stale scalar.
Run: python -m pytest tests/test_live_seek.py
"""
import os
import shutil
import tempfile
import threading
import unittest
from unittest import mock

from app.processors import live
from app.processors.live import LiveTranslationEngine, covered_through, merge_interval, next_uncovered
from app.processors.video import VideoProcessor


class TestMergeInterval(unittest.TestCase):
    def test_merges_touching_intervals(self):
        self.assertEqual(merge_interval([[0, 25]], 25, 50), [[0, 50]])

    def test_merges_overlapping_intervals(self):
        self.assertEqual(merge_interval([[10, 20]], 15, 30), [[10, 30]])

    def test_insertion_keeps_list_sorted(self):
        self.assertEqual(merge_interval([[50, 60], [0, 10]], 20, 30),
                         [[0, 10], [20, 30], [50, 60]])

    def test_zero_length_interval_is_ignored(self):
        self.assertEqual(merge_interval([[0, 10]], 10, 10), [[0, 10]])


class TestNextUncovered(unittest.TestCase):
    def test_empty_coverage_returns_window_start(self):
        self.assertEqual(next_uncovered([], 5.0, 30.0), 5.0)

    def test_fully_covered_window_returns_none(self):
        self.assertIsNone(next_uncovered([[0, 50]], 5.0, 30.0))

    def test_hole_inside_window_returns_hole_start(self):
        self.assertEqual(next_uncovered([[0, 10], [20, 50]], 5.0, 30.0), 10.0)

    def test_hole_before_window_is_ignored(self):
        self.assertEqual(next_uncovered([[0, 10], [20, 50]], 15.0, 18.0), 15.0)

    def test_gap_at_window_end_is_returned(self):
        self.assertEqual(next_uncovered([[0, 10]], 5.0, 30.0), 10.0)

    def test_empty_window_returns_none(self):
        self.assertIsNone(next_uncovered([[0, 10]], 10.0, 10.0))


class TestCoveredThrough(unittest.TestCase):
    def test_returns_end_of_contiguous_run(self):
        self.assertEqual(covered_through([[0, 50], [80, 100]], 10.0), 50.0)

    def test_position_in_a_hole_returns_zero(self):
        self.assertEqual(covered_through([[0, 10], [20, 30]], 15.0), 0.0)

    def test_position_before_all_coverage_returns_zero(self):
        self.assertEqual(covered_through([[10, 20]], 0.0), 0.0)


class _FakeTranslation:
    def translate_chunk(self, segments, source_lang, target_lang, context=None):
        return [{"start": s["start"], "end": s["end"], "text": "t" + s["text"]} for s in segments]


class TestSeekCoverage(unittest.TestCase):
    def setUp(self):
        self.wav_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.wav_dir, True)
        with mock.patch.object(VideoProcessor, "get_duration", return_value=400.0):
            self.engine = LiveTranslationEngine("/tmp/none.mp4", "ja", "en")
        self.engine._load_models = mock.Mock()
        self.engine.translation_service = _FakeTranslation()
        self.engine._reported_state = "Playing"
        self.engine._whisper_call = lambda wav, offset, language=None: [
            {"start": offset, "end": offset + 5, "text": f"seg{offset:.0f}"}
        ]
        self.engine._write_srt = mock.Mock()
        self.extracted = []

    def _run(self):
        with mock.patch.object(live.vad, "get_speech_regions", return_value=[(0.0, 1.0)]), \
                mock.patch.object(live, "_release_gpu_memory"):
            worker = threading.Thread(target=self.engine._run, daemon=True)
            worker.start()
            worker.join(10)
        self.assertFalse(worker.is_alive())

    def test_steady_playback_extracts_contiguous_chunks(self):
        def fake_extract(video_path, start, end):
            self.extracted.append((start, end))
            if len(self.extracted) == 2:
                self.engine._stop_flag = True
            path = os.path.join(self.wav_dir, f"chunk_{start}_{end}.wav")
            open(path, "w").close()
            return path

        self.engine.video_processor.extract_audio_segment = fake_extract
        self._run()

        self.assertEqual(self.extracted, [(0.0, 25.0), (25.0, 50.0)])
        self.assertEqual(self.engine.covered, [[0.0, 50.0]])

    def test_rewind_into_hole_restarts_extraction_there(self):
        def fake_extract(video_path, start, end):
            self.extracted.append((start, end))
            path = os.path.join(self.wav_dir, f"chunk_{start}_{end}.wav")
            open(path, "w").close()
            if start == 25:
                self.engine.update_position(300.0, "Playing")
            elif start == 300:
                self.engine.update_position(100.0, "Playing")
            elif start == 100:
                self.engine._stop_flag = True
            return path

        self.engine.video_processor.extract_audio_segment = fake_extract
        self._run()

        self.assertEqual(self.extracted,
                         [(0.0, 25.0), (25.0, 50.0), (300.0, 325.0), (100.0, 125.0)])
        texts = [s["text"] for s in self.engine.segments]
        self.assertEqual(len(texts), len(set(texts)))


if __name__ == "__main__":
    unittest.main()

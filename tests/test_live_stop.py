"""Live engine stop lifecycle (audit item 6).

Contract C2: stop() returns True only after the worker thread exited (its
finally released models) and returns False while the worker is still running —
in that case nothing the worker reads is touched.
Run: python -m pytest tests/test_live_stop.py
"""
import os
import threading
import unittest
from unittest import mock

from app.processors import live
from app.processors.live import LiveTranslationEngine
from app.processors.video import VideoProcessor


def _make_engine(**overrides):
    with mock.patch.object(VideoProcessor, "get_duration", return_value=100.0):
        engine = LiveTranslationEngine("/tmp/none.mp4", "ja", "en", session_id="test")
    for key, value in overrides.items():
        setattr(engine, key, value)
    return engine


class TestStopLifecycle(unittest.TestCase):
    def test_stop_before_start_returns_true(self):
        self.assertTrue(_make_engine().stop())

    def test_stop_returns_false_while_worker_runs(self):
        engine = _make_engine()
        sentinel = object()
        engine.translation_service = sentinel
        release = threading.Event()
        engine._thread = threading.Thread(target=release.wait, daemon=True)
        engine._thread.start()
        try:
            self.assertFalse(engine.stop(timeout_s=0.2))
            self.assertIs(engine.translation_service, sentinel)
            self.assertNotIn("[Live] Stopped", engine.logs)
        finally:
            release.set()
            engine._thread.join(5)

    def test_second_stop_returns_true_after_worker_exits(self):
        engine = _make_engine()
        release = threading.Event()
        engine._thread = threading.Thread(target=release.wait, daemon=True)
        engine._thread.start()
        self.assertFalse(engine.stop(timeout_s=0.1))
        release.set()
        self.assertTrue(engine.stop(timeout_s=5))

    def test_stopped_run_releases_models_in_finally(self):
        engine = _make_engine()
        fake_whisper = mock.Mock()
        engine._load_models = mock.Mock(side_effect=lambda: (
            setattr(engine, "_whisper_proc", fake_whisper),
            setattr(engine, "translation_service", object()),
        ))
        engine._thread = threading.Thread(target=engine._run, daemon=True)
        with mock.patch.object(live, "_release_gpu_memory"):
            engine._thread.start()
            engine._stop_flag = True
            engine._thread.join(5)

        self.assertFalse(engine._thread.is_alive())
        self.assertIsNone(engine.translation_service)
        self.assertIsNone(engine._whisper_proc)
        fake_whisper.terminate.assert_called_once()

    def test_model_load_failure_releases_and_records_error(self):
        engine = _make_engine()
        engine.translation_service = object()
        engine._load_models = mock.Mock(side_effect=RuntimeError("boom"))
        with mock.patch.object(live, "_release_gpu_memory"):
            engine._run()

        self.assertIsNone(engine.translation_service)
        self.assertIn("Model loading failed: boom", engine._error)

    def test_fatal_error_path_cleans_up_exactly_once(self):
        engine = _make_engine()
        engine.translation_service = object()
        engine._reported_state = "Playing"
        engine._max_consecutive_errors = 3
        engine._load_models = mock.Mock()
        engine.video_processor.extract_audio_segment = mock.Mock(side_effect=RuntimeError("no audio"))

        calls = []
        original = engine._release_models

        def spy():
            calls.append(1)
            original()

        engine._release_models = spy
        with mock.patch.object(live, "_release_gpu_memory"), \
                mock.patch.object(live.time, "sleep", lambda _s: None):
            engine._run()

        self.assertEqual(engine._consecutive_errors, 3)
        self.assertEqual(len(calls), 1)
        self.assertIsNone(engine.translation_service)


class TestConstructorNaming(unittest.TestCase):
    def test_output_basename_overrides_the_temp_name(self):
        with mock.patch.object(VideoProcessor, "get_duration", return_value=100.0):
            engine = LiveTranslationEngine("/tmp/tmpa9x7b2c1.mp4", "ja", "en",
                                           output_basename="My_Clip")
        self.assertEqual(os.path.basename(engine.srt_file_path), "My_Clip_live.en.srt")

    def test_falls_back_to_the_source_name(self):
        with mock.patch.object(VideoProcessor, "get_duration", return_value=100.0):
            engine = LiveTranslationEngine("/tmp/clip.mp4", "ja", "en")
        self.assertEqual(os.path.basename(engine.srt_file_path), "clip_live.en.srt")


if __name__ == "__main__":
    unittest.main()

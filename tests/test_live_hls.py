"""Live HLS readiness (audit item 7).

A completed conversion must mark the playlist ready even when the source is
shorter than the 4s mid-progress flip; success without a playlist is surfaced
as an error, and an aborted conversion never claims readiness.
Run: python -m pytest tests/test_live_hls.py
"""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from app.processors import live
from app.processors.live import LiveTranslationEngine
from app.processors.video import VideoProcessor


class _FakeProc:
    def __init__(self, lines, code=0):
        self.stdout = iter(lines)
        self._code = code
        self.terminated = False
        self.killed = False

    def wait(self):
        return self._code

    def poll(self):
        return None

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


class TestHlsReady(unittest.TestCase):
    def _engine(self, duration=3.0, transcode=True):
        with mock.patch.object(VideoProcessor, "get_duration", return_value=duration):
            engine = LiveTranslationEngine("/tmp/clip.mp4", "ja", "en",
                                           transcode_to_h264=transcode, session_id="hls-test")
        hls_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, hls_dir, True)
        engine.hls_dir = hls_dir
        return engine, hls_dir

    def _run_transcode(self, engine, proc):
        with mock.patch.object(live.subprocess, "Popen", return_value=proc):
            engine._transcode()

    def test_short_success_marks_playlist_ready(self):
        engine, hls_dir = self._engine(duration=3.0)
        open(os.path.join(hls_dir, "playlist.m3u8"), "w").close()
        self._run_transcode(engine, _FakeProc(["out_time_ms=1000000\n"]))

        self.assertTrue(engine.hls_ready)
        self.assertEqual(engine.transcode_progress, 100.0)
        self.assertIsNone(engine.transcode_error)

    def test_success_without_playlist_is_an_error(self):
        engine, _ = self._engine()
        self._run_transcode(engine, _FakeProc(["out_time_ms=1000000\n"]))

        self.assertFalse(engine.hls_ready)
        self.assertEqual(engine.transcode_progress, 100.0)
        self.assertIn("without producing a playlist", engine.transcode_error)

    def test_mid_progress_flip_still_marks_ready(self):
        engine, hls_dir = self._engine(duration=30.0)
        open(os.path.join(hls_dir, "playlist.m3u8"), "w").close()
        self._run_transcode(engine, _FakeProc(["out_time_ms=5000000\n"]))

        self.assertTrue(engine.hls_ready)
        self.assertEqual(engine.transcode_progress, 100.0)

    def test_stopped_conversion_never_marks_ready(self):
        engine, hls_dir = self._engine()
        open(os.path.join(hls_dir, "playlist.m3u8"), "w").close()
        engine._stop_flag = True
        proc = _FakeProc(["out_time_ms=1000000\n"])
        self._run_transcode(engine, proc)

        self.assertTrue(proc.terminated)
        self.assertFalse(engine.hls_ready)
        self.assertLess(engine.transcode_progress, 100.0)


if __name__ == "__main__":
    unittest.main()

"""Live chunk handling: one finally owns the temp WAV (audit item 14).

Silent chunks used to `continue` before the WAV cleanup. Every path — silent,
VAD failure, transcription, exception — must delete the file, and only real
transcription/silence advances coverage.
Run: python -m pytest tests/test_live_chunks.py
"""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from app.processors import live
from app.processors.live import LiveTranslationEngine
from app.processors.video import VideoProcessor


class _FakeTranslation:
    def translate_chunk(self, segments, source_lang, target_lang, context=None):
        return [{"start": s["start"], "end": s["end"], "text": "t" + s["text"]} for s in segments]


class TestChunkWaveCleanup(unittest.TestCase):
    def setUp(self):
        self.wav_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.wav_dir, True)
        with mock.patch.object(VideoProcessor, "get_duration", return_value=100.0):
            self.engine = LiveTranslationEngine("/tmp/none.mp4", "ja", "en")
        self.engine._load_models = mock.Mock()
        self.engine.translation_service = _FakeTranslation()
        self.engine._reported_state = "Playing"
        self.engine._write_srt = mock.Mock()
        self.wav_path = os.path.join(self.wav_dir, "chunk.wav")

    def _extract_once(self):
        """First (and only) extraction creates a real WAV and stops the loop after it."""
        def fake_extract(video_path, start, end):
            open(self.wav_path, "w").close()
            self.engine._stop_flag = True
            return self.wav_path
        self.engine.video_processor.extract_audio_segment = fake_extract

    def _run(self, speech_regions):
        with mock.patch.object(live.vad, "get_speech_regions", return_value=speech_regions), \
                mock.patch.object(live, "_release_gpu_memory"):
            self.engine._run()

    def test_silent_chunk_removes_wav_and_marks_coverage(self):
        self._extract_once()
        self.engine._whisper_call = mock.Mock()
        self._run([])

        self.assertFalse(os.path.exists(self.wav_path))
        self.engine._whisper_call.assert_not_called()
        self.assertEqual(self.engine.covered, [[0.0, 25.0]])

    def test_transcription_failure_removes_wav_without_coverage(self):
        self._extract_once()
        self.engine._max_consecutive_errors = 1
        self.engine._whisper_call = mock.Mock(side_effect=RuntimeError("asr down"))
        self._run([(0.0, 1.0)])

        self.assertFalse(os.path.exists(self.wav_path))
        self.assertEqual(self.engine._consecutive_errors, 1)
        self.assertEqual(self.engine.covered, [])

    def test_normal_chunk_removes_wav_and_marks_coverage(self):
        self._extract_once()
        self.engine._whisper_call = mock.Mock(return_value=[
            {"start": 0.0, "end": 5.0, "text": "hello"}
        ])
        self._run([(0.0, 1.0)])

        self.assertFalse(os.path.exists(self.wav_path))
        self.assertEqual(self.engine.covered, [[0.0, 25.0]])
        self.assertEqual(len(self.engine.segments), 1)

    def test_video_only_source_advances_coverage_without_removal(self):
        def fake_extract(video_path, start, end):
            self.engine._stop_flag = True
            return None
        self.engine.video_processor.extract_audio_segment = fake_extract
        self.engine._whisper_call = mock.Mock()

        with mock.patch.object(live.os, "remove") as remove:
            self._run([(0.0, 1.0)])

        remove.assert_not_called()
        self.engine._whisper_call.assert_not_called()
        self.assertEqual(self.engine.covered, [[0.0, 25.0]])


if __name__ == "__main__":
    unittest.main()

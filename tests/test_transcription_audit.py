"""Unit tests for the transcription audit logic
(repetition-loop detector, retry-pass kwargs, hallucination drop rule).

Run: python -m pytest tests/test_transcription_audit.py
Design contract: docs/TRANSCRIPTION_PIPELINE.md
"""
import unittest

from app.config import settings
from app.processors.transcription import TranscriptionService


class TestRepetitionLoop(unittest.TestCase):
    """Audit doctrine: detect ASR loops purely via audit logic, then the code
    re-transcribes the region (never LLM-repairs the text)."""

    def test_clean_dialogue_not_flagged(self):
        self.assertFalse(TranscriptionService._is_repetition_loop(
            "Yesterday we went to the market together and bought lots of fresh vegetables for the trip",
            "She promised to visit her grandmother before traveling to Osaka next weekend",
        ))

    def test_consecutive_identical_segments_flagged(self):
        seg = "the order of the day is the annual budget report from the finance committee"
        self.assertTrue(TranscriptionService._is_repetition_loop(seg, seg))

    def test_heavily_connected_repetition_flagged(self):
        # Two segments sharing most of their 3-grams
        a = "the city council voted unanimously on the new parking ordinance yesterday morning"
        b = "the city council voted unanimously on the new parking ordinance today morning"
        self.assertTrue(TranscriptionService._is_repetition_loop(a, b))

    def test_single_short_emphatic_repeat_not_flagged(self):
        # Emphatic one-off repetition is normal speech; segments too short to
        # be flagged conservatively
        a = "and then he said it to me once more"
        b = "that's right, that's right"
        self.assertFalse(TranscriptionService._is_repetition_loop(a, b))

    def test_short_segments_never_flagged(self):
        # Fewer than 4 tokens per side: keep conservatively (no retry)
        self.assertFalse(TranscriptionService._is_repetition_loop("hello there again", "okay"))

    def test_intra_segment_loop_flagged(self):
        # Same 3-gram appearing twice inside one segment
        text = "he said the answer the answer the answer to everything"
        self.assertTrue(TranscriptionService._is_repetition_loop("", text))


class TestHallucinationDrop(unittest.TestCase):
    def test_boilerplate_dropped(self):
        self.assertTrue(
            TranscriptionService._is_hallucination("Thank you.", 0.95)
        )

    def test_real_speech_kept(self):
        self.assertFalse(
            TranscriptionService._is_hallucination(
                "This is a real sentence that goes on quite a bit longer than boilerplate", 0.95)
        )
        self.assertFalse(
            TranscriptionService._is_hallucination("Thank you. We will get started.", 0.2)
        )


class TestAnnealKwargs(unittest.TestCase):
    """Item 3: retry pass adds temperature ladder + patience; pass-1 untouched."""

    def test_pass1_kwargs_untouched(self):
        svc = TranscriptionService.__new__(TranscriptionService)
        kwargs = svc._whisper_kwargs("en")
        self.assertNotIn("temperature", kwargs)
        self.assertNotIn("patience", kwargs)

    def test_retry_kwargs_anneal(self):
        svc = TranscriptionService.__new__(TranscriptionService)
        kwargs = svc._whisper_kwargs("en", beam_size=settings.WHISPER_RETRY_BEAM_SIZE,
                                     anneal=True)
        self.assertEqual(kwargs["beam_size"], settings.WHISPER_RETRY_BEAM_SIZE)
        self.assertEqual(
            kwargs["temperature"],
            [t.strip() for t in settings.WHISPER_RETRY_TEMPERATURE.split(",")],
        )
        self.assertEqual(kwargs["patience"], settings.WHISPER_RETRY_PATIENCE)


if __name__ == "__main__":
    unittest.main()

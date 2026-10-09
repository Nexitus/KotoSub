import unittest
from app.config import settings
from app.processors.transcription import TranscriptionService
from app.processors.translation import TranslationService


class TestHallucinationFilter(unittest.TestCase):
    def setUp(self):
        self.ts = TranscriptionService.__new__(TranscriptionService)

    def test_drops_no_speech_boilerplate(self):
        self.assertTrue(self.ts._is_hallucination("Thank you.", 0.95))

    def test_keeps_real_speech(self):
        self.assertFalse(
            self.ts._is_hallucination("Thank you for watching this longer sentence", 0.95))
        self.assertFalse(self.ts._is_hallucination("Thank you.", 0.5))


class TestSuspectFlagging(unittest.TestCase):
    def setUp(self):
        self.svc = TranslationService.__new__(TranslationService)

    def test_low_confidence_transcript_flagged(self):
        seg = {"text": "hello", "original": "bonjour",
               "avg_logprob": settings.WHISPER_RETRY_LOGPROB - 0.1}
        self.assertTrue(self.svc._is_suspect(seg))

    def test_good_transcript_not_flagged(self):
        seg = {"text": "hello", "original": "bonjour", "avg_logprob": -0.2}
        self.assertFalse(self.svc._is_suspect(seg))

    def test_missing_logprob_ignored(self):
        seg = {"text": "hello", "original": "bonjour"}
        self.assertFalse(self.svc._is_suspect(seg))


if __name__ == "__main__":
    unittest.main()

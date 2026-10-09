import unittest
from app.processors.subtitles import SubtitleGenerator


class TestSubtitleTiming(unittest.TestCase):
    def setUp(self):
        self.gen = SubtitleGenerator()

    def test_word_snap_and_buffers(self):
        segs = [{
            "start": 1.0, "end": 8.0,  # whisper bounds overshoot speech
            "text": "hello world", "speaker": None,
            "words": [
                {"start": 1.5, "end": 2.0, "word": "hello"},
                {"start": 2.5, "end": 3.0, "word": "world"},
            ],
        }]
        polished = self.gen.polish_timing(segs, duration=10.0)
        self.assertAlmostEqual(polished[0]["start"], 1.5 - 0.12)
        self.assertAlmostEqual(polished[0]["end"], 3.0 + 0.35)

    def test_clamps_to_duration_and_zero(self):
        segs = [{
            "start": 0.0, "end": 12.0, "text": "hi", "speaker": None,
            "words": [{"start": 0.02, "end": 11.8, "word": "hi"}],
        }]
        polished = self.gen.polish_timing(segs, duration=11.9)
        self.assertEqual(polished[0]["start"], 0.0)
        self.assertAlmostEqual(polished[0]["end"], 11.9)

    def test_no_overlap(self):
        segs = [
            {"start": 1.0, "end": 5.0, "text": "a", "speaker": None,
             "words": [{"start": 2.0, "end": 4.0, "word": "a"}]},
            {"start": 4.2, "end": 6.0, "text": "b", "speaker": None,
             "words": [{"start": 4.3, "end": 5.0, "word": "b"}]},
        ]
        polished = self.gen.polish_timing(segs, duration=10.0)
        self.assertLessEqual(polished[0]["end"], polished[1]["start"])

    def test_wordless_untouched(self):
        segs = [{"start": 1.0, "end": 2.0, "text": "x", "speaker": None}]
        polished = self.gen.polish_timing(segs, duration=10.0)
        self.assertEqual((polished[0]["start"], polished[0]["end"]), (1.0, 2.0))


if __name__ == "__main__":
    unittest.main()

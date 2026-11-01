"""Contracts for run-scoped speaker splitting (A→B→A):

- each child of a split segment carries only the words of its own maximal
  consecutive same-speaker run (no word leaks across same-speaker runs)
- polished timings derived from those words stay ordered and non-negative
- children partition the parent's words exactly: none duplicated, none lost
- boundary rule: straddling word → larger overlap, exact tie → earlier turn
- word in a gap between turns inherits the previous word's speaker
"""
import unittest
from app.config import settings
from app.processors.diarization import DiarizationService
from app.processors.subtitles import SubtitleGenerator

TURNS = [
    {"start": 0.0, "end": 2.0, "speaker": "A"},
    {"start": 2.0, "end": 4.0, "speaker": "B"},
    {"start": 4.0, "end": 6.0, "speaker": "A"},
]

TEXT = "Hello there well maybe hello again"

WORDS = [
    {"start": 0.5, "end": 0.8, "word": "Hello"},
    {"start": 0.9, "end": 1.2, "word": "there"},
    {"start": 2.2, "end": 2.5, "word": "well"},
    {"start": 2.6, "end": 2.9, "word": "maybe"},
    {"start": 4.2, "end": 4.5, "word": "hello"},
    {"start": 4.6, "end": 4.9, "word": "again"},
]


def make_service(turns):
    """Service without model loading (object.__new__ skips the HF pipeline)."""
    svc = object.__new__(DiarizationService)
    svc.exclusive_turns = turns
    return svc


def make_seg(words, text):
    return {
        "start": words[0]["start"], "end": words[-1]["end"],
        "text": text, "speaker": None,
        "words": [dict(w) for w in words],
    }


def word_texts(child):
    return [w["word"] for w in child["words"]]


def split(words, text, turns=TURNS):
    svc = make_service(turns)
    return svc.split_segments_at_speaker_changes([make_seg(words, text)])


class TestOwnRunWords(unittest.TestCase):
    def test_each_child_gets_only_its_own_run_words(self):
        out = split(WORDS, TEXT)
        self.assertEqual([s["speaker"] for s in out], ["A", "B", "A"])
        self.assertEqual(word_texts(out[0]), ["Hello", "there"])
        self.assertEqual(word_texts(out[1]), ["well", "maybe"])
        self.assertEqual(word_texts(out[2]), ["hello", "again"])
        self.assertNotIn("hello", word_texts(out[0]))
        self.assertNotIn("again", word_texts(out[0]))
        self.assertNotIn("Hello", word_texts(out[2]))
        self.assertNotIn("there", word_texts(out[2]))

    def test_child_texts_and_times_follow_their_run(self):
        out = split(WORDS, TEXT)
        self.assertEqual([s["text"] for s in out],
                         ["Hello there", "well maybe", "hello again"])
        self.assertEqual(out[0]["start"], 0.5)
        self.assertEqual(out[0]["end"], 1.2)
        self.assertEqual(out[1]["start"], 2.2)
        self.assertEqual(out[1]["end"], 2.9)
        self.assertEqual(out[2]["start"], 4.2)
        self.assertEqual(out[2]["end"], 4.9)


class TestPolishedTiming(unittest.TestCase):
    def test_polished_windows_are_ordered_and_non_negative(self):
        lead = settings.SUBTITLE_LEAD_IN_SECONDS
        trail = settings.SUBTITLE_TRAIL_SECONDS
        out = split(WORDS, TEXT)
        polished = SubtitleGenerator().polish_timing(out, duration=6.0)
        expected = [
            (0.5 - lead, 1.2 + trail),
            (2.2 - lead, 2.9 + trail),
            (4.2 - lead, 4.9 + trail),
        ]
        for seg, (start, end) in zip(polished, expected):
            self.assertAlmostEqual(seg["start"], start, places=6)
            self.assertAlmostEqual(seg["end"], end, places=6)
            self.assertGreaterEqual(seg["end"], seg["start"])
        starts = [s["start"] for s in polished]
        self.assertEqual(starts, sorted(starts))
        self.assertEqual(len(set(starts)), len(starts))

    def test_adjacent_runs_never_polish_to_negative_duration(self):
        # touching word bounds at the A/B turn edge: no gap to absorb the lead-in
        words = [
            {"start": 1.8, "end": 2.0, "word": "aa"},
            {"start": 2.0, "end": 2.2, "word": "bb"},
            {"start": 4.2, "end": 4.4, "word": "cc"},
        ]
        out = split(words, "aa bb cc")
        self.assertEqual([s["speaker"] for s in out], ["A", "B", "A"])
        polished = SubtitleGenerator().polish_timing(out, duration=6.0)
        for seg in polished:
            self.assertGreaterEqual(seg["end"] - seg["start"], 0.0)


class TestWordPartition(unittest.TestCase):
    def test_children_partition_parent_words_in_order(self):
        seg = make_seg(WORDS, TEXT)
        out = make_service(TURNS).split_segments_at_speaker_changes([seg])
        rebuilt = [w for child in out for w in child["words"]]
        self.assertEqual(rebuilt, seg["words"])


class TestBoundaryRules(unittest.TestCase):
    def test_straddling_word_goes_to_turn_with_more_overlap(self):
        # [1.8, 2.3]: 0.2s in A, 0.3s in B → B
        words = [
            {"start": 1.5, "end": 1.7, "word": "first"},
            {"start": 1.8, "end": 2.3, "word": "cross"},
            {"start": 2.4, "end": 2.6, "word": "next"},
        ]
        out = split(words, "first cross next")
        self.assertEqual([s["speaker"] for s in out], ["A", "B"])
        self.assertEqual(word_texts(out[0]), ["first"])
        self.assertEqual(word_texts(out[1]), ["cross", "next"])

    def test_exact_tie_goes_to_earlier_turn(self):
        # [1.75, 2.25]: 0.25s in each turn → earlier turn (A)
        words = [
            {"start": 1.4, "end": 1.6, "word": "aa"},
            {"start": 1.75, "end": 2.25, "word": "tie"},
            {"start": 2.4, "end": 2.6, "word": "bb"},
        ]
        out = split(words, "aa tie bb")
        self.assertEqual([s["speaker"] for s in out], ["A", "B"])
        self.assertEqual(word_texts(out[0]), ["aa", "tie"])
        self.assertEqual(word_texts(out[1]), ["bb"])

    def test_gap_word_inherits_previous_speaker(self):
        turns = [
            {"start": 0.0, "end": 2.0, "speaker": "A"},
            {"start": 2.0, "end": 3.9, "speaker": "B"},
            {"start": 4.1, "end": 6.0, "speaker": "A"},
        ]
        # [3.95, 4.05] overlaps no turn → carries B into the B run
        words = [
            {"start": 2.5, "end": 2.7, "word": "aa"},
            {"start": 3.95, "end": 4.05, "word": "gap"},
            {"start": 4.2, "end": 4.4, "word": "bb"},
        ]
        out = split(words, "aa gap bb", turns=turns)
        self.assertEqual([s["speaker"] for s in out], ["B", "A"])
        self.assertEqual(word_texts(out[0]), ["aa", "gap"])
        self.assertEqual(word_texts(out[1]), ["bb"])


if __name__ == "__main__":
    unittest.main()

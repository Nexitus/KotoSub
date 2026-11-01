"""Regression contracts for speaker separation (diarization → subtitles):

- assign_speakers(): maximal temporal overlap, not midpoint containment
- split_segments_at_speaker_changes(): word-level regrouping so a subtitle
  line never carries two voices; wordless segments and un-rebuildable text
  pass through intact (fidelity guard)
- SRT/VTT rendering: dialogue dash opens each new speaker turn; explicit
  speaker ids never leak into output text; single-speaker or diarization-off
  output stays dash-free and byte-compatible with the legacy renderer
- ASS: speaker id only in the invisible Name field; None never leaks
"""
import unittest
from app.processors.diarization import DiarizationService
from app.processors.subtitles import SubtitleGenerator

DASH = "\u2013"

TURNS = [
    {"start": 0.0, "end": 2.55, "speaker": "SPEAKER_00"},
    {"start": 2.55, "end": 4.5, "speaker": "SPEAKER_01"},
]

WORDS = [
    {"start": 1.80, "end": 2.00, "word": "I"},
    {"start": 2.00, "end": 2.18, "word": "told"},
    {"start": 2.20, "end": 2.38, "word": "you"},
    {"start": 2.38, "end": 2.55, "word": "so."},
    {"start": 2.60, "end": 2.80, "word": "Okay"},
    {"start": 2.80, "end": 3.00, "word": "forget"},
    {"start": 3.00, "end": 3.20, "word": "it."},
]


def make_service(turns):
    """Service without model loading; diarize() is what fills exclusive_turns.
    (object.__new__ skips __init__ so no HF pipeline load happens in tests.)"""
    svc = object.__new__(DiarizationService)
    svc.exclusive_turns = turns
    return svc


class TestAssignSpeakers(unittest.TestCase):
    def setUp(self):
        self.svc = make_service(TURNS)

    def test_straddle_takes_dominant_side(self):
        seg = [{"start": 1.8, "end": 3.2, "text": "x", "speaker": None}]
        self.svc.assign_speakers(seg, TURNS)
        # overlap: 00→0.75s, 01→0.65s
        self.assertEqual(seg[0]["speaker"], "SPEAKER_00")

    def test_turn_held_most_wins_even_if_shorter_turn_wraps_midpoint(self):
        turns = [
            {"start": 0.0, "end": 10.0, "speaker": "A"},   # old midpoint bug: hit here
            {"start": 10.0, "end": 10.4, "speaker": "B"},
        ]
        seg = [{"start": 10.0, "end": 10.4, "text": "hi", "speaker": None}]
        self.svc.assign_speakers(seg, turns)
        self.assertEqual(seg[0]["speaker"], "B")

    def test_outside_all_turns_stays_unlabeled(self):
        seg = [{"start": 20.0, "end": 21.0, "text": "x", "speaker": None}]
        self.svc.assign_speakers(seg, TURNS)
        self.assertIsNone(seg[0]["speaker"])

    def test_empty_turns_is_noop(self):
        segs = [{"start": 0.0, "end": 1.0, "text": "x", "speaker": None}]
        self.svc.assign_speakers(segs, [])
        self.assertIsNone(segs[0]["speaker"])


class TestSplitAtHandoffs(unittest.TestCase):
    def setUp(self):
        self.svc = make_service(TURNS)

    def _seg(self, words, text, start=1.8, end=3.2):
        return {"start": start, "end": end, "text": text,
                "words": [dict(w) for w in words], "speaker": None}

    def test_handoff_becomes_two_cues(self):
        out = self.svc.split_segments_at_speaker_changes(
            [self._seg(WORDS, "I told you so. Okay forget it.")])
        self.assertEqual([s["speaker"] for s in out],
                         ["SPEAKER_00", "SPEAKER_01"])
        self.assertEqual(out[0]["text"], "I told you so.")
        self.assertEqual(out[0]["end"], 2.55)
        self.assertEqual(out[1]["text"], "Okay forget it.")
        self.assertEqual(out[1]["start"], 2.60)
        self.assertEqual(out[0]["words"][-1]["word"], "so.")

    def test_wordless_segment_passes_through_whole(self):
        seg = {"start": 1.8, "end": 3.2, "text": "I told you so. Okay forget it.",
               "words": [], "speaker": None}
        seg = self.svc.assign_speakers([seg], TURNS)[0]
        out = self.svc.split_segments_at_speaker_changes([seg])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "I told you so. Okay forget it.")

    def test_unrebuildable_text_stays_whole(self):
        # words no longer map into the text → fidelity guard refuses to split
        seg = self._seg(WORDS, "Completely different text")
        out = self.svc.split_segments_at_speaker_changes([seg])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["text"], "Completely different text")

    def test_single_speaker_segment_unsplit(self):
        svc = make_service([TURNS[0]])  # one turn only
        out = svc.split_segments_at_speaker_changes(
            [self._seg(WORDS, "I told you so. Okay forget it.")])
        self.assertEqual(len(out), 1)

    def test_cjk_glues_like_source_text(self):
        words = [
            {"start": 1.80, "end": 2.10, "word": "おはよう"},
            {"start": 2.10, "end": 2.20, "word": "ございます。"},
            {"start": 2.20, "end": 2.50, "word": "はい"},
            {"start": 2.60, "end": 2.70, "word": "、"},
            {"start": 2.70, "end": 3.00, "word": "そうですね。"},
        ]
        out = self.svc.split_segments_at_speaker_changes(
            [self._seg(words, "おはようございます。はい、そうですね。")])
        self.assertEqual(out[0]["text"], "おはようございます。はい")
        self.assertEqual(out[0]["speaker"], "SPEAKER_00")
        self.assertEqual(out[1]["speaker"], "SPEAKER_01")


class TestRendering(unittest.TestCase):
    def setUp(self):
        self.gen = SubtitleGenerator()
        svc = make_service(TURNS)
        self.split = svc.split_segments_at_speaker_changes(
            svc.assign_speakers(
                [{"start": 1.8, "end": 3.2, "text": "I told you so. Okay forget it.",
                  "words": [dict(w) for w in WORDS], "speaker": None},
                 {"start": 3.6, "end": 4.2, "text": "Sure thing.",
                  "words": [{"start": 3.60, "end": 3.90, "word": "Sure"},
                            {"start": 3.90, "end": 4.20, "word": "thing."}],
                  "speaker": None}],
                TURNS))

    def test_srt_dash_opens_each_turn_no_ids(self):
        srt = self.gen.generate_srt(self.split)
        self.assertNotIn("SPEAKER_", srt)
        # both speakers' opening lines carry the dash…
        self.assertIn(f"{DASH} I told you so.", srt)
        self.assertIn(f"{DASH} Okay forget it.", srt)
        # …same-speaker continuations do not
        self.assertNotIn(f"{DASH} Sure thing.", srt)

    def test_single_speaker_transcript_has_no_dash(self):
        svc = make_service([TURNS[0]])
        segs = [{"start": 0.0, "end": 2.0, "text": "only me here",
                 "words": [{"start": 0.1, "end": 1.9, "word": "only me here"}],
                 "speaker": None}]
        out = svc.assign_speakers(segs, [TURNS[0]])
        self.assertNotIn(DASH, self.gen.generate_srt(out))

    def test_diarization_off_output_unchanged(self):
        segs = [{"start": 0, "end": 2, "text": "Hello world.", "speaker": None}]
        srt = self.gen.generate_srt(segs)
        vtt = self.gen.generate_vtt(segs)
        self.assertNotIn("[SPEAKER", srt)
        self.assertNotIn(DASH, srt)
        self.assertNotIn("<v ", vtt)
        self.assertIn("WEBVTT", vtt)

    def test_ass_speaker_only_in_name_field(self):
        ass = self.gen.generate_ass(self.split)
        self.assertNotIn(DASH, ass)
        self.assertIn(",SPEAKER_01,", ass)  # Name field, invisible
        none_ass = self.gen.generate_ass(
            [{"start": 0, "end": 1, "text": "x", "speaker": None}])
        self.assertIn(",Default,", none_ass)
        self.assertNotIn(",None,", none_ass)

    def test_vtt_no_voice_spans(self):
        vtt = self.gen.generate_vtt(self.split)
        self.assertNotIn("<v ", vtt)
        self.assertIn(f"{DASH} Okay forget it.", vtt)


if __name__ == "__main__":
    unittest.main()

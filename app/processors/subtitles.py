import os
from typing import List, Dict, Any
from app.config import settings

def is_cjk_char(ch: str) -> bool:
    """True for Hiragana/Katakana, CJK ideographs (incl. Ext A), Hangul, CJK compat."""
    code = ord(ch)
    return (0x3040 <= code <= 0x30FF or   # Hiragana / Katakana
            0x3400 <= code <= 0x4DBF or   # CJK Ext A
            0x4E00 <= code <= 0x9FFF or   # CJK Unified
            0xAC00 <= code <= 0xD7AF or   # Hangul
            0xF900 <= code <= 0xFAFF)     # CJK Compat

class SubtitleGenerator:
    def generate_srt(self, segments: List[Dict[str, Any]]) -> str:
        """
        Generates an SRT content string from segments.
        Includes speaker identification if available.
        """
        blocks = []
        for i, seg in enumerate(segments, 1):
            text = seg['text']
            if seg.get('speaker'):
                text = f"[{seg['speaker']}]: {text}"
            blocks.append(
                f"{i}\n"
                f"{self._fmt_time(seg['start'])} --> {self._fmt_time(seg['end'])}\n"
                f"{text}"
            )
        return "\n".join(blocks)

    def generate_vtt(self, segments: List[Dict[str, Any]]) -> str:
        """
        Feature 6: Generates WebVTT content (standard for web players).
        """
        output = ["WEBVTT\n"]
        for i, seg in enumerate(segments):
            text = seg['text']

            if seg.get('speaker'):
                text = f"<v {seg['speaker']}>{text}</v>"

            output.append(f"{i+1}")
            output.append(f"{self._fmt_time(seg['start'], ms_sep='.')} --> {self._fmt_time(seg['end'], ms_sep='.')}")
            output.append(f"{text}")
            output.append("") # Empty line between segments

        return "\n".join(output)

    # Natural break points for space-less scripts (Japanese, Chinese...)
    CJK_PUNCTUATION = "、。！？…，；：・」』）〉》!?,.:;"

    def _cjk_ratio(self, text: str) -> float:
        if not text:
            return 0.0
        cjk = sum(1 for ch in text if is_cjk_char(ch))
        return cjk / max(1, len(text))

    def polish_timing(self, segments: List[Dict[str, Any]], duration: float = None) -> List[Dict[str, Any]]:
        """
        Snaps display windows to real word timestamps with a small lead-in and
        linger buffer, instead of raw Whisper segment bounds (which often
        include the silence up to the next segment, so subtitles hang on).
        Wordless segments are left untouched (except duration clamp).
        """
        lead = settings.SUBTITLE_LEAD_IN_SECONDS
        trail = settings.SUBTITLE_TRAIL_SECONDS
        out = []
        for seg in segments:
            s = dict(seg)
            words = s.get('words') or []
            if words:
                s['start'] = max(0.0, words[0]['start'] - lead)
                s['end'] = words[-1]['end'] + trail
            if duration is not None:
                s['end'] = min(s['end'], duration)
            out.append(s)
        # No-overlap pass: word-snap can push a window past the next one
        for prev, nxt in zip(out, out[1:]):
            if prev['end'] > nxt['start']:
                prev['end'] = nxt['start']
        return out

    def refine_segments(self, segments: List[Dict[str, Any]], max_cps: int = None) -> List[Dict[str, Any]]:
        """
        Feature 7: Refines segments for better readability and timing.
        Splits segments exceeding the characters-per-second threshold.

        Split timing is anchored to real word timestamps (from Whisper) when
        available; split points in the text prefer natural boundaries — spaces
        for spaced scripts, punctuation marks for CJK scripts.
        """
        max_cps = max_cps or settings.SUBTITLE_MAX_CPS
        cjk_cps = settings.SUBTITLE_MAX_CPS_CJK
        if not segments:
            return []

        refined = []
        for seg in segments:
            self._refine_segment(dict(seg), refined, max_cps, cjk_cps, depth=0)
        return refined

    def _refine_segment(self, seg: Dict[str, Any], out: List[Dict[str, Any]],
                        max_cps: int, cjk_cps: int, depth: int) -> None:
        text = (seg.get('text') or '').strip()
        seg['text'] = text
        duration = seg['end'] - seg['start']

        limit = cjk_cps if self._cjk_ratio(text) >= 0.4 else max_cps
        # Never split into parts shorter than SUBTITLE_MIN_SPLIT_SECONDS —
        # flash-frames are worse than a briefly dense subtitle.
        if (duration <= 0 or depth >= 3 or not text
                or duration < 2 * settings.SUBTITLE_MIN_SPLIT_SECONDS
                or len(text) / duration <= limit):
            out.append(seg)
            return

        split_time, text1, text2 = self._find_split(seg, text, duration)
        if text1 is None:
            out.append(seg)
            return

        min_part = settings.SUBTITLE_MIN_SPLIT_SECONDS
        if not (seg['start'] + min_part <= split_time <= seg['end'] - min_part):
            split_time = seg['start'] + duration / 2  # fall back to even halves
        if not (seg['start'] + min_part <= split_time <= seg['end'] - min_part):
            out.append(seg)
            return

        left = {
            "start": seg['start'],
            "end": split_time,
            "text": text1,
            "original": seg.get('original', ''),
            "speaker": seg.get('speaker')
        }
        right = {
            "start": split_time,
            "end": seg['end'],
            "text": text2,
            "original": seg.get('original', ''),
            "speaker": seg.get('speaker')
        }
        self._refine_segment(left, out, max_cps, cjk_cps, depth + 1)
        self._refine_segment(right, out, max_cps, cjk_cps, depth + 1)

    def _find_split(self, seg: Dict[str, Any], text: str, duration: float):
        """Finds a (split_time, text1, text2) triple for splitting a segment in
        half. Returns (None, None, None) when no natural split point exists."""
        fraction = 0.5

        # 1. Time: snap the proportional target to the nearest real inter-word
        #    gap when word timestamps are available.
        split_time = seg['start'] + duration * fraction
        words = seg.get('words') or []
        if len(words) >= 2:
            target_time = split_time
            best_gap = None
            best_delta = None
            for i in range(1, len(words)):
                gap_start = words[i - 1]['end']
                gap_end = words[i]['start']
                if gap_end <= gap_start:
                    continue
                mid = (gap_start + gap_end) / 2
                if not (seg['start'] < mid < seg['end']):
                    continue
                delta = abs(mid - target_time)
                if best_delta is None or delta < best_delta:
                    best_delta = delta
                    best_gap = mid
            if best_gap is not None:
                split_time = best_gap

        # 2. Text: split at the natural boundary closest to the same fraction.
        candidates = set()
        for pos in range(1, len(text)):
            prev_ch, next_ch = text[pos - 1], text[pos]
            if prev_ch in (" ", "\t"):
                candidates.add(pos)
            elif prev_ch in self.CJK_PUNCTUATION:
                candidates.add(pos)            # break after punctuation
            elif next_ch in self.CJK_PUNCTUATION:
                candidates.add(pos + 1)        # break after punctuation
        candidates = sorted(c for c in candidates if 1 <= c < len(text))
        if not candidates:
            return None, None, None

        target_pos = fraction * len(text)
        pos = min(candidates, key=lambda c: abs(c - target_pos))
        text1 = text[:pos].strip()
        text2 = text[pos:].strip()
        if not text1 or not text2:
            return None, None, None

        return split_time, text1, text2

    def generate_ass(self, segments: List[Dict[str, Any]]) -> str:
        """
        Feature 6: Generates ASS content (Advanced Substation Alpha).
        """
        header = "[Script Info]\nScriptType: v4.00+\nPlayResX: 384\nPlayResY: 288\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        events = []
        for seg in segments:
            start = self._fmt_time(seg['start'], ms_sep='.', ms_digits=2, hour_pad=1)
            end = self._fmt_time(seg['end'], ms_sep='.', ms_digits=2, hour_pad=1)
            text = seg['text'].replace('\n', '\\N')
            speaker = str(seg.get('speaker', 'Default'))
            events.append(f"Dialogue: 0,{start},{end},Default,{speaker},0,0,0,,{text}")

        return header + "\n".join(events)

    @staticmethod
    def _fmt_time(seconds: float, ms_sep: str = ",", ms_digits: int = 3, hour_pad: int = 2) -> str:
        """Formats seconds as H(ish):MM:SS<sep>fraction — SRT (','/3/2), VTT ('.'/3/2), ASS ('.'/2/1)."""
        scale = 10 ** ms_digits
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        frac = int((seconds - int(seconds)) * scale)
        return f"{hours:0{hour_pad}d}:{minutes:02d}:{secs:02d}{ms_sep}{frac:0{ms_digits}d}"

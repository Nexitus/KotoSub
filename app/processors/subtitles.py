import os
from typing import List, Dict, Any
import pysrt
from app.config import settings

class SubtitleGenerator:
    def generate_srt(self, segments: List[Dict[str, Any]]) -> str:
        """
        Generates an SRT content string from segments.
        Includes speaker identification if available.
        """
        subs = pysrt.SubRipFile()
        
        for i, seg in enumerate(segments):
            start = self._seconds_to_subriptime(seg['start'])
            end = self._seconds_to_subriptime(seg['end'])
            
            text = seg['text']
            if seg.get('speaker'):
                text = f"[{seg['speaker']}]: {text}"
            
            item = pysrt.SubRipItem(index=i+1, start=start, end=end, text=text)
            subs.append(item)
        
        # Joining segments manually to ensure correct SRT format
        return "\n".join(str(item) for item in subs)

    def generate_ass(self, segments: List[Dict[str, Any]]) -> str:
        """
        Feature 6: Generates ASS content (Advanced Substation Alpha).
        """
        header = "[Script Info]\nScriptType: v4.00+\nPlayResX: 384\nPlayResY: 288\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        events = []
        for seg in segments:
            start = self._seconds_to_ass_time(seg['start'])
            end = self._seconds_to_ass_time(seg['end'])
            text = seg['text'].replace('\n', '\\N')
            speaker = str(seg.get('speaker', 'Default'))
            events.append(f"Dialogue: 0,{start},{end},Default,{speaker},0,0,0,,{text}")
        
        return header + "\n".join(events)

    def refine_segments(self, segments: List[Dict[str, Any]], max_cps: int = 20) -> List[Dict[str, Any]]:
        """
        Feature 7: Refines segments for better readability and timing.
        Splits segments if they exceed characters-per-second (CPS) threshold.
        """
        if not segments:
            return []

        refined = []
        for seg in segments:
            # Basic refinement: remove leading/trailing noise
            text = seg['text'].strip()
            duration = seg['end'] - seg['start']
            
            if duration > 0 and (len(text) / duration) > max_cps and " " in text:
                # Logic to split into two halves
                words = text.split(" ")
                midpoint = len(words) // 2
                
                text1 = " ".join(words[:midpoint])
                text2 = " ".join(words[midpoint:])
                
                # Split time proportionally
                split_time = seg['start'] + (duration * (len(text1) / len(text)))
                
                refined.append({
                    "start": seg['start'],
                    "end": split_time,
                    "text": text1,
                    "original": seg.get('original', ''),
                    "speaker": seg.get('speaker')
                })
                refined.append({
                    "start": split_time,
                    "end": seg['end'],
                    "text": text2,
                    "original": seg.get('original', ''),
                    "speaker": seg.get('speaker')
                })
            else:
                seg['text'] = text
                refined.append(seg)
                
        return refined

    def _seconds_to_subriptime(self, seconds: float) -> pysrt.SubRipTime:
        """
        Helper to convert float seconds to pysrt.SubRipTime
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        
        return pysrt.SubRipTime(hours, minutes, secs, millis)

    def _seconds_to_ass_time(self, seconds: float) -> str:
        """
        Helper for ASS time format: H:MM:SS.cc
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"

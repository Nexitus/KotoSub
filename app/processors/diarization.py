import os
from typing import List, Dict, Any
try:
    from pyannote.audio import Pipeline
    import torch
except Exception as e:
    Pipeline = None
    print(f"Warning: Could not load Diarization dependencies (pyannote.audio/torch). Diarization will be disabled. Error: {e}")

class DiarizationService:
    def __init__(self, auth_token: str = None):
        self.auth_token = auth_token or os.getenv("HF_AUTH_TOKEN")
        self.pipeline = None
        if Pipeline and self.auth_token:
            try:
                self.pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    use_auth_token=self.auth_token
                )
                if torch.cuda.is_available():
                    self.pipeline.to(torch.device("cuda"))
            except Exception as e:
                print(f"Failed to load pyannote pipeline: {e}")

    def diarize(self, audio_path: str) -> List[Dict[str, Any]]:
        """
        Identifies speaker segments in the audio.
        Returns a list of {start, end, speaker_id}.
        """
        if not self.pipeline:
            print("Diarization pipeline not initialized (check HF_AUTH_TOKEN).")
            return []

        diarization = self.pipeline(audio_path)
        
        segments = []
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segments.append({
                "start": turn.start,
                "end": turn.end,
                "speaker": speaker
            })
        return segments

    def assign_speakers(self, transcript_segments: List[Dict[str, Any]], diarization_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Assigns the most likely speaker to each transcript segment based on overlap.
        """
        if not diarization_segments:
            return transcript_segments

        for t_seg in transcript_segments:
            t_mid = (t_seg['start'] + t_seg['end']) / 2
            # Find the speaker active at the midpoint of the transcript segment
            for d_seg in diarization_segments:
                if d_seg['start'] <= t_mid <= d_seg['end']:
                    t_seg['speaker'] = d_seg['speaker']
                    break
        return transcript_segments

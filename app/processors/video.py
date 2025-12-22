import os
import ffmpeg
from app.config import settings

class VideoProcessor:
    def validate_video(self, filepath: str) -> bool:
        """
        Validates if the file exists and is a valid video file.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        
        try:
            probe = ffmpeg.probe(filepath)
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
            
            if not video_stream:
                raise ValueError("No video stream found in file.")
            
            # Warning: Some videos might not have audio, but for this app it's critical
            if not audio_stream:
                raise ValueError("No audio stream found in file.")
                
            return True
        except ffmpeg.Error as e:
            raise ValueError(f"Invalid video file: {e.stderr.decode() if e.stderr else str(e)}")

    def extract_audio(self, video_path: str, denoise: bool = True, normalize: bool = True) -> str:
        """
        Extracts audio from video and applies pre-processing filters.
        """
        filename = os.path.splitext(os.path.basename(video_path))[0]
        output_path = os.path.join(settings.TEMP_DIR, f"{filename}.wav")
        
        # Build ffmpeg filters
        filters = []
        if denoise:
            # highpass/lowpass is a simple way, or afftdn for noise reduction
            filters.append("afftdn=nf=-25")
        if normalize:
            # loudnorm for EBU R128 normalization
            filters.append("loudnorm")
            
        filter_str = ",".join(filters)
        
        try:
            input_node = ffmpeg.input(video_path)
            audio = input_node.audio
            
            if denoise:
                audio = audio.filter("afftdn", nf=-25)
            if normalize:
                audio = audio.filter("loudnorm")
                
            (
                ffmpeg
                .output(audio, output_path, acodec='pcm_s16le', ac=1, ar='16k')
                .run(overwrite_output=True, capture_stdout=True, capture_stderr=True)
            )
            return output_path
        except ffmpeg.Error as e:
            raise RuntimeError(f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")

    def get_duration(self, video_path: str) -> float:
        """
        Returns the duration of the video in seconds.
        """
        try:
            probe = ffmpeg.probe(video_path)
            return float(probe['format']['duration'])
        except (ffmpeg.Error, KeyError, ValueError):
            return 0.0

    def burn_subtitles(self, video_path: str, subtitles_path: str, output_path: str, font: str = "Arial", font_size: int = 24, position: str = "Bottom Center", shadow: float = 1.0, outline: float = 1.0) -> str:
        """
        Re-encodes the video with burnt-in subtitles.
        """
        try:
            # Map friendly position names to ASS alignment values
            # 1=Left/Bot, 2=Center/Bot, 3=Right/Bot, 5=Top/Left, 6=Top/Center, 7=Top/Right
            # 9=Left/Mid, 10=Center/Mid, 11=Right/Mid
            align_map = {
                "Bottom Left": 1,
                "Bottom Center": 2,
                "Bottom Right": 3,
                "Top Left": 7, # ASS 7 is top-left
                "Top Center": 6, 
                "Top Right": 9, # Wait, ASS alignment is numpad based. 7=TopLeft, 8=TopCenter, 9=TopRight.
                "Center": 5
            }
            # Correcting alignment based on ASS spec (Numpad)
            # 1: Bottom Left, 2: Bottom Center, 3: Bottom Right
            # 4: Left Center, 5: Center, 6: Right Center
            # 7: Top Left, 8: Top Center, 9: Top Right
            
            # Using specific overrides map
            numpad_align = {
                "Bottom Left": 1, "Bottom Center": 2, "Bottom Right": 3,
                "Left Center": 4, "Center": 5, "Right Center": 6,
                "Top Left": 7, "Top Center": 8, "Top Right": 9
            }
            
            alignment = numpad_align.get(position, 2)
            
            # Build force_style string
            # Warning: Windows paths in ffmpeg filter require escaping.
            # It's safer to use forward slashes for the path in the filter string.
            subs_path_safe = subtitles_path.replace("\\", "/").replace(":", "\\:")

            style = f"FontName={font},FontSize={font_size},Alignment={alignment},Outline={outline},Shadow={shadow}"

            (
                ffmpeg
                .input(video_path)
                .output(output_path, vf=f"subtitles='{subs_path_safe}':force_style='{style}'", vcodec='libx264', acodec='aac')
                .run(overwrite_output=True, quiet=True)
            )
            return output_path
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            print(f"FFmpeg burn-in error: {error_msg}")
            raise RuntimeError(f"Failed to burn subtitles: {error_msg}")

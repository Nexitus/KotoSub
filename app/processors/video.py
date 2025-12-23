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

    def burn_subtitles(self, video_path: str, subtitles_path: str, output_path: str, 
                       font: str = "Arial", font_size: int = 24, position: str = "Bottom Center", 
                       shadow: float = 1.0, outline: float = 1.0, use_gpu: bool = False) -> str:
        """
        Re-encodes the video with burnt-in subtitles.
        If use_gpu is True, attempts to use NVENC (HEVC). Falls back to libx264 (CPU) on failure.
        """
        # Map friendly position names to ASS alignment values
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
        
        def run_ffmpeg(vcodec, preset=None):
            stream = ffmpeg.input(video_path)
            kwargs = {
                'vf': f"subtitles='{subs_path_safe}':force_style='{style}'",
                'vcodec': vcodec,
                'acodec': 'aac'
            }
            if preset:
                kwargs['preset'] = preset
                
            (
                stream
                .output(output_path, **kwargs)
                .run(overwrite_output=True, quiet=False) # Show output or at least don't swallow it
            )

        try:
            if use_gpu:
                try:
                    print(f"[Video] Attempting encoding with hevc_nvenc for: {os.path.basename(output_path)}")
                    run_ffmpeg('hevc_nvenc', preset='p4') # p4 is medium preset for NVENC
                    print("[Video] NVENC encoding successful.")
                    return output_path
                except ffmpeg.Error as e:
                    print(f"[Video] NVENC encoding failed or not available: {e.stderr.decode() if e.stderr else str(e)}")
                    print("[Video] Falling back to CPU encoding (libx264)...")
            
            # CPU fallback or default
            print(f"[Video] Starting CPU encoding (libx264) for: {os.path.basename(output_path)}")
            run_ffmpeg('libx264')
            print("[Video] CPU encoding successful.")
            return output_path
            
        except ffmpeg.Error as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            print(f"FFmpeg burn-in fatal error: {error_msg}")
            raise RuntimeError(f"Failed to burn subtitles: {error_msg}")

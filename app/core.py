import os
import uuid
from typing import Dict, Any
from app.processors.video import VideoProcessor
from app.processors.transcription import TranscriptionService
from app.processors.translation import TranslationService
from app.processors.subtitles import SubtitleGenerator
from app.processors.diarization import DiarizationService
from app.config import settings

class VideoTranslatorApp:
    def __init__(self):
        self.video_processor = VideoProcessor()
        self.subtitle_generator = SubtitleGenerator()
        # DiarizationService initialized lazily/per-request to support dynamic tokens

    def process(self, video_path: str, source_lang: str = None, target_lang: str = "en", 
                openai_api_key: str = None, openai_base_url: str = None, 
                whisper_model: str = None, llm_model: str = None,
                output_dir: str = None,
                use_diarization: bool = True,
                hf_token: str = None,
                use_quality_check: bool = True,
                burn_subtitles: bool = False,
                burn_options: Dict[str, Any] = None,
                progress_callback=None) -> Dict[str, Any]:
        """
        Orchestrates the entire translation process.
        """
        # Initialize services with dynamic config
        transcription_service = TranscriptionService(
            api_key=openai_api_key, 
            base_url=openai_base_url,
            model=whisper_model
        )
        translation_service = TranslationService(
            api_key=openai_api_key, 
            base_url=openai_base_url,
            model=llm_model
        )
        
        # Initialize Diarization with provided token
        diarization_service = DiarizationService(auth_token=hf_token)
        
        job_id = str(uuid.uuid4())
        
        # 1. Validation
        if progress_callback: progress_callback(0.1, "Validating video...")
        self.video_processor.validate_video(video_path)
        
        # 2. Extract Audio
        if progress_callback: progress_callback(0.2, "Extracting audio (this may take a moment)...")
        audio_path = self.video_processor.extract_audio(video_path)
        duration = self.video_processor.get_duration(video_path)
        
        try:
            # 3. Transcribe
            if progress_callback: progress_callback(0.4, "Transcribing audio...")
            transcript_segments = transcription_service.transcribe(audio_path, language=source_lang)
            
            # 3a. Diarization (Feature 1)
            if use_diarization:
                if progress_callback: progress_callback(0.5, "Identifying speakers (Diarization)...")
                diarization_segments = diarization_service.diarize(audio_path)
                transcript_segments = diarization_service.assign_speakers(transcript_segments, diarization_segments)

            # 4. Translate (Feature 8: Expanded Target Support)
            if progress_callback: progress_callback(0.6, "Translating text...")
            translated_segments = translation_service.translate(
                transcript_segments, 
                source_lang=source_lang or "auto", 
                target_lang=target_lang
            )
            
            # 4a. AI Quality Verification Pass (Feature 4)
            if use_quality_check:
                if progress_callback: progress_callback(0.7, "Verifying translation quality...")
                translated_segments = translation_service.quality_check(translated_segments, source_lang, target_lang)

            # 4b. Intelligent Segment Refinement (Feature 7)
            if progress_callback: progress_callback(0.75, "Refining subtitles for readability...")
            translated_segments = self.subtitle_generator.refine_segments(translated_segments)

            # 5. Generate Subtitle (Feature 6: Advanced Formats support)
            if progress_callback: progress_callback(0.8, "Generating subtitles...")
            subtitle_content = self.subtitle_generator.generate_srt(translated_segments)
            
            # Save to file
            final_output_dir = output_dir if output_dir else settings.OUTPUT_DIR
            os.makedirs(final_output_dir, exist_ok=True)
            filename = os.path.splitext(os.path.basename(video_path))[0]
            output_file = os.path.join(final_output_dir, f"{filename}_{target_lang}.srt")
            
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(subtitle_content)

            # 6. Burn Subtitles (Optional)
            video_output_file = None
            if burn_subtitles:
                if progress_callback: progress_callback(0.9, "Burning subtitles into video (this triggers re-encode)...")
                burn_opts = burn_options or {}
                video_output_file = os.path.join(final_output_dir, f"{filename}_{target_lang}_burned.mp4")
                self.video_processor.burn_subtitles(
                    video_path=video_path,
                    subtitles_path=output_file,
                    output_path=video_output_file,
                    font=burn_opts.get("font", "Arial"),
                    font_size=burn_opts.get("font_size", 24),
                    position=burn_opts.get("position", "Bottom Center"),
                    shadow=burn_opts.get("shadow", 1.0),
                    outline=burn_opts.get("outline", 1.0)
                )
            
            if progress_callback: progress_callback(1.0, "Done!")
            
            return {
                "job_id": job_id,
                "status": "completed",
                "output_file": output_file,
                "video_output": video_output_file,
                "duration": duration,
                "segments": len(translated_segments)
            }
            
        finally:
            # Cleanup audio file
            if os.path.exists(audio_path):
                os.remove(audio_path)

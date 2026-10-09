import os
import uuid
from typing import Dict, Any
from app.processors.video import VideoProcessor
from app.processors.transcription import create_transcription_service
from app.processors.translation import TranslationService
from app.processors.subtitles import SubtitleGenerator
from app.processors.diarization import DiarizationService
from app.config import settings

def _release_gpu_memory():
    """
    Frees GPU memory after a model is no longer needed.
    Critical on 16 GB GPUs: models must be loaded one at a time,
    otherwise VRAM exhaustion causes 'invalid resource handle' errors.
    """
    import gc
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass

class VideoTranslatorApp:
    def __init__(self):
        self.video_processor = VideoProcessor()
        self.subtitle_generator = SubtitleGenerator()
        # DiarizationService initialized lazily/per-request to support dynamic tokens

    def process(self, video_path: str, source_lang: str = None, target_lang: str = "en",
                whisper_model: str = None, llm_model: str = None,
                local_llm_file: str = None,
                whisper_prompt: str = None, whisper_hotwords: str = None,
                output_dir: str = None,
                use_diarization: bool = True,
                hf_token: str = None,
                use_quality_check: bool = True,
                burn_subtitles: bool = False,
                burn_options: Dict[str, Any] = None,
                use_gpu_encoding: bool = False,
                subtitle_format: str = "srt",
                output_suffix: str = "_translated",
                include_language_in_name: bool = True,
                progress_callback=None) -> Dict[str, Any]:
        """
        Orchestrates the entire translation process.
        """
        import sys
        import io

        # Feature 13: LogStream to capture stdout and send to frontend
        # IMPORTANT: We duplicate stdout instead of redirecting it so logs appear in both terminal and frontend
        class LogStream(io.StringIO):
            def __init__(self, callback, original_stdout):
                super().__init__()
                self.callback = callback
                self.original_stdout = original_stdout
            def write(self, s):
                # Write to terminal
                if self.original_stdout:
                    self.original_stdout.write(s)
                    self.original_stdout.flush()
                # Send to frontend
                if s.strip() and self.callback:
                    self.callback(None, s, step="log")
                return super().write(s)

        old_stdout = sys.stdout
        log_capture = LogStream(progress_callback, old_stdout)
        sys.stdout = log_capture

        try:
            # Release any VRAM left over from a previous request (e.g. an LLM
            # that wasn't garbage-collected yet). On 16 GB GPUs this is critical —
            # even a few hundred MiB of stale allocation can cause Whisper to fail
            # with "CUDA failed with error invalid resource handle".
            _release_gpu_memory()
            
            job_id = str(uuid.uuid4())
            
            # 1. Validation
            if progress_callback: progress_callback(0.05, "Validating video...", step="validation")
            self.video_processor.validate_video(video_path)
            
            # 2. Extract Audio
            if progress_callback: progress_callback(0.1, "Extracting audio...", step="extraction")
            audio_path = self.video_processor.extract_audio(video_path)
            duration = self.video_processor.get_duration(video_path)
            
            # 3. Transcribe — Whisper is the ONLY model in VRAM.
            #    The LLM is loaded after transcription so they never compete for VRAM.
            if progress_callback: progress_callback(0.2, "Transcribing audio content...", step="transcription")
            transcription_service = create_transcription_service(model=whisper_model)
            transcript_segments, transcription_meta = transcription_service.transcribe(
                audio_path, language=source_lang,
                initial_prompt=whisper_prompt, hotwords=whisper_hotwords
            )
            if transcription_meta.get("retry_regions"):
                print(f"[Transcription] {transcription_meta['retry_regions']} flagged region(s) retried.")
            del transcription_service
            _release_gpu_memory()
            
            # 3a. Diarization (Feature 1) — loaded only if enabled, released after use
            if use_diarization:
                if progress_callback: progress_callback(0.35, "Identifying speakers (Diarization)...", step="diarization")
                diarization_service = DiarizationService(auth_token=hf_token)
                diarization_segments = diarization_service.diarize(audio_path)
                transcript_segments = diarization_service.assign_speakers(transcript_segments, diarization_segments)
                del diarization_service
                _release_gpu_memory()

            # 4. Translate (Feature 8) — LLM is now the ONLY model in VRAM
            if progress_callback: progress_callback(0.45, f"Translating to {target_lang}...", step="translation")
            translation_service = TranslationService(model=llm_model, local_file=local_llm_file)

            seg_total = max(len(transcript_segments), 1)
            seg_done = {"n": 0}

            def on_segment(seg):
                seg_done["n"] += 1
                if progress_callback:
                    progress_callback(
                        0.45 + 0.15 * seg_done["n"] / seg_total,
                        f"Translating segment {seg_done['n']}/{seg_total}",
                        step="translation",
                        segment=seg,
                    )

            translated_segments = translation_service.translate(
                transcript_segments,
                source_lang=source_lang or "auto",
                target_lang=target_lang,
                segment_callback=on_segment,
            )
            
            # 4a. AI Quality Verification Pass (Feature 4) — reuses the already-loaded LLM
            if use_quality_check:
                if progress_callback: progress_callback(0.6, "Verifying translation quality...", step="quality_check")
                translated_segments = translation_service.quality_check(translated_segments, source_lang or "auto", target_lang)
            del translation_service
            _release_gpu_memory()

            # 4b. Timing polish + Intelligent Segment Refinement (Feature 7)
            # Polish runs first so split children inherit the buffered outer
            # edges while split boundaries stay bare at the word gap.
            if progress_callback: progress_callback(0.7, "Refining subtitles for readability...", step="refinement")
            polished_segments = self.subtitle_generator.polish_timing(translated_segments, duration)
            refined_segments = self.subtitle_generator.refine_segments(polished_segments)

            # 5. Generate Subtitle (Feature 6)
            if progress_callback: progress_callback(0.8, "Generating subtitle file...", step="generation")
            
            if subtitle_format == "ass":
                subtitle_content = self.subtitle_generator.generate_ass(refined_segments)
                ext = "ass"
            elif subtitle_format == "vtt":
                subtitle_content = self.subtitle_generator.generate_vtt(refined_segments)
                ext = "vtt"
            else:
                subtitle_content = self.subtitle_generator.generate_srt(refined_segments)
                ext = "srt"
            
            # Save to file (Feature 12: Custom Naming)
            final_output_dir = output_dir if output_dir else settings.OUTPUT_DIR
            os.makedirs(final_output_dir, exist_ok=True)
            
            base_filename = os.path.splitext(os.path.basename(video_path))[0]
            final_suffix = output_suffix
            if include_language_in_name:
                final_suffix += f"_{target_lang}"
            
            output_file = os.path.join(final_output_dir, f"{base_filename}{final_suffix}.{ext}")
            
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(subtitle_content)

            # 6. Burn Subtitles (Optional)
            video_output_file = None
            if burn_subtitles:
                if progress_callback: progress_callback(0.85, "Burning subtitles into video...", step="burn_in")
                burn_opts = burn_options or {}
                video_output_file = os.path.join(final_output_dir, f"{base_filename}{final_suffix}.mp4")
                self.video_processor.burn_subtitles(
                    video_path=video_path,
                    subtitles_path=output_file,
                    output_path=video_output_file,
                    font=burn_opts.get("font", "Arial"),
                    font_size=burn_opts.get("font_size", 24),
                    position=burn_opts.get("position", "Bottom Center"),
                    shadow=burn_opts.get("shadow", 1.0),
                    outline=burn_opts.get("outline", 1.0),
                    use_gpu=use_gpu_encoding
                )
            
            if progress_callback: progress_callback(1.0, "Done!", step="completed")
            
            return {
                "job_id": job_id,
                "status": "completed",
                "output_file": output_file,
                "video_output": video_output_file,
                "duration": duration,
                "segments": len(refined_segments),
                # Transcription audit trail (docs/TRANSCRIPTION_PIPELINE.md):
                "transcription_meta": {
                    "dropped_count": len(transcription_meta.get("dropped", [])),
                    "retry_regions": transcription_meta.get("retry_regions", 0),
                }
            }
            
        finally:
            # Restore stdout
            sys.stdout = old_stdout
            # Drop references to any services that may still be in scope so
            # gc.collect() can free their GPU memory before the next request.
            try:
                del transcription_service
            except NameError:
                pass
            try:
                del translation_service
            except NameError:
                pass
            try:
                del diarization_service
            except NameError:
                pass
            _release_gpu_memory()
            # Cleanup audio file
            if 'audio_path' in locals() and os.path.exists(audio_path):
                os.remove(audio_path)

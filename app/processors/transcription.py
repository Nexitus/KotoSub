from typing import List, Dict, Any
from openai import OpenAI
import os
import torch
import sys
from app.config import settings

def _fix_cuda_paths():
    """
    Helper to find and add NVIDIA DLLs to the PATH on Windows.
    Solves 'Could not locate cudnn_ops64_9.dll' and similar issues.
    """
    if sys.platform != "win32":
        return

    import site
    packages_dirs = site.getsitepackages()
    if hasattr(site, "getusersitepackages"):
        packages_dirs.append(site.getusersitepackages())
    
    # Common subfolders where nvidia-cudnn-cu12 and nvidia-cublas-cu12 store DLLs
    nvidia_dirs = [
        "nvidia/cudnn/bin",
        "nvidia/cublas/bin",
        "nvidia/cuda_runtime/bin",
        "nvidia/cuda_nvrtc/bin"
    ]
    
    found_any = False
    for base in packages_dirs:
        for ndir in nvidia_dirs:
            full_path = os.path.join(base, ndir)
            if os.path.exists(full_path):
                print(f"[CUDA Fix] Adding to PATH: {full_path}")
                os.environ["PATH"] = full_path + os.pathsep + os.environ["PATH"]
                if hasattr(os, "add_dll_directory"):
                    try:
                        os.add_dll_directory(full_path)
                    except Exception:
                        pass
                found_any = True
    
    if not found_any:
        print("[CUDA Fix] Warning: No NVIDIA library paths found in site-packages. DLL errors may occur.")

class TranscriptionService:
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None, use_local: bool = False):
        self.use_local = use_local
        self.model = model or (settings.LOCAL_WHISPER_MODEL if use_local else settings.WHISPER_MODEL)
        
        if self.use_local:
            _fix_cuda_paths()
            print(f"[Transcription] Initializing Local Whisper Model: {self.model}")
            # Import here to avoid loading if not used
            from faster_whisper import WhisperModel
            
            # Helper to determine device
            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"[Transcription] Using device: {device}")
            
            # Compute type: 'float16' best for CUDA, 'int8' for CPU
            compute_type = "float16" if device == "cuda" else "int8"
            
            try:
                self.local_client = WhisperModel(self.model, device=device, compute_type=compute_type, download_root=settings.MODELS_DIR)
            except Exception as e:
                print(f"[Transcription] Error loading local model: {e}")
                raise RuntimeError(f"Failed to load local Whisper model: {e}")
        else:
            if not api_key:
                api_key = settings.OPENAI_API_KEY
            
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url or settings.OPENAI_BASE_URL,
                default_headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            )

    # Mapping from Whisper's returned language names to ISO-639-1 codes
    LANGUAGE_NAME_TO_CODE = {
        "english": "en", "chinese": "zh", "german": "de", "spanish": "es", "russian": "ru", 
        "korean": "ko", "french": "fr", "japanese": "ja", "portuguese": "pt", "turkish": "tr",
        "polish": "pl", "catalan": "ca", "dutch": "nl", "arabic": "ar", "swedish": "sv", 
        "italian": "it", "indonesian": "id", "hindi": "hi", "finnish": "fi", "vietnamese": "vi", 
        "hebrew": "he", "ukrainian": "uk", "greek": "el", "malay": "ms", "czech": "cs", 
        "romanian": "ro", "danish": "da", "hungarian": "hu", "tamil": "ta", "norwegian": "no", 
        "thai": "th", "urdu": "ur", "croatian": "hr", "bulgarian": "bg", "lithuanian": "lt", 
        "latin": "la", "maori": "mi", "malayalam": "ml", "welsh": "cy", "slovak": "sk", 
        "telugu": "te", "persian": "fa", "latvian": "lv", "bengali": "bn", "serbian": "sr", 
        "azerbaijani": "az", "slovenian": "sl", "kannada": "kn", "estonian": "et", 
        "macedonian": "mk", "breton": "br", "basque": "eu", "icelandic": "is", "armenian": "hy", 
        "nepali": "ne", "mongolian": "mn", "bosnian": "bs", "kazakh": "kk", "albanian": "sq", 
        "swahili": "sw", "galician": "gl", "marathi": "mr", "sinhala": "si", 
        "khmer": "km", "shona": "sn", "yoruba": "yo", "somali": "so", "afrikaans": "af", 
        "occitan": "oc", "georgian": "ka", "belarusian": "be", "tajik": "tg", "sindhi": "sd", 
        "gujarati": "gu", "amharic": "am", "yiddish": "yi", "lao": "lo", "uzbek": "uz", 
        "faroese": "fo", "haitian creole": "ht", "pashto": "ps", "turkmen": "tk", 
        "nynorsk": "nn", "maltese": "mt", "sanskrit": "sa", "luxembourgish": "lb", 
        "myanmar": "my", "tibetan": "bo", "tagalog": "tl", "malagasy": "mg", "assamese": "as", 
        "tatar": "tt", "hawaiian": "haw", "lingala": "ln", "hausa": "ha", "bashkir": "ba", 
        "javanese": "jw", "sundanese": "su", "cantonese": "yue",
    }

    def transcribe(self, audio_path: str, language: str = None) -> List[Dict[str, Any]]:
        """
        Transcribes audio file using OpenAI Whisper API or Local Faster-Whisper.
        """
        # Normalize language input
        if language:
            language = language.lower().strip()
            if language == 'auto':
                language = None
            else:
                language = self.LANGUAGE_NAME_TO_CODE.get(language, language)

        if self.use_local:
            return self._transcribe_local(audio_path, language)
        else:
            return self._transcribe_api(audio_path, language)

    def _transcribe_local(self, audio_path: str, language: str = None) -> List[Dict[str, Any]]:
        print(f"[Transcription] Starting local transcription for {os.path.basename(audio_path)}")
        
        try:
            segments, info = self.local_client.transcribe(
                audio_path, 
                language=language,
                beam_size=5
            )
            
            print(f"[Transcription] Detected language: {info.language} with probability {info.language_probability}")
            
            all_segments = []
            # faster-whisper returns a generator, so we iterate
            # We don't know the total count beforehand from the generator,
            # but we can log as they arrive.
            for i, segment in enumerate(segments):
                idx = i + 1
                print(f"[Whisper] Local segment {idx} processed: [{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text.strip()[:50]}...")
                all_segments.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                    "speaker": None
                })
            
            print(f"[Transcription] Local transcription complete. Found {len(all_segments)} segments.")
            return all_segments
            
        except Exception as e:
            print(f"[Transcription] Local transcription error: {e}")
            raise e

    def _transcribe_api(self, audio_path: str, language: str = None) -> List[Dict[str, Any]]:
        from pydub import AudioSegment
        import math

        # Load audio
        audio = AudioSegment.from_file(audio_path)
        duration_ms = len(audio)
        chunk_length_ms = 10 * 60 * 1000  # 10 minutes
        chunks_count = math.ceil(duration_ms / chunk_length_ms)
        
        all_segments = []
        detected_language = None
        
        for i in range(chunks_count):
            start_ms = i * chunk_length_ms
            end_ms = min((i + 1) * chunk_length_ms, duration_ms)
            
            # Export chunk
            chunk = audio[start_ms:end_ms]
            chunk_filename = f"{audio_path}_{i}.mp3"
            chunk.export(chunk_filename, format="mp3")
            
            try:
                with open(chunk_filename, "rb") as audio_file:
                    lang_param = language
                    if not lang_param and detected_language:
                        lang_param = self.LANGUAGE_NAME_TO_CODE.get(detected_language.lower(), detected_language)
                    
                    print(f"[Whisper] Transcribing chunk {i+1}/{chunks_count} ({os.path.basename(chunk_filename)})...")
                    transcript = self.client.audio.transcriptions.create(
                        model=self.model,
                        file=audio_file,
                        language=lang_param,
                        response_format="verbose_json"
                    )
                    print(f"[Whisper] Completed chunk {i+1}. Segments found: {len(getattr(transcript, 'segments', []))}")

                if i == 0 and not language:
                    detected_language = getattr(transcript, 'language', None)
                    print(f"Auto-detected language: {detected_language}")

                time_offset_s = start_ms / 1000.0
                
                if hasattr(transcript, 'segments'):
                    for seg in transcript.segments:
                        if isinstance(seg, dict):
                            start = seg.get('start', 0)
                            end = seg.get('end', 0)
                            text = seg.get('text', "")
                        else:
                            start = getattr(seg, 'start', 0)
                            end = getattr(seg, 'end', 0)
                            text = getattr(seg, 'text', "")
                        
                        all_segments.append({
                            "start": start + time_offset_s,
                            "end": end + time_offset_s,
                            "text": text.strip(),
                            "speaker": None
                        })
                else:
                    all_segments.append({
                        "start": time_offset_s,
                        "end": (end_ms / 1000.0),
                        "text": transcript.text,
                        "speaker": None
                    })
                    
            except Exception as e:
                print(f"Error transcribing chunk {i}: {e}")
                raise e
            finally:
                if os.path.exists(chunk_filename):
                    os.remove(chunk_filename)
             
        return all_segments

from typing import List, Dict, Any
from openai import OpenAI
import os
from app.config import settings

class TranscriptionService:
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        if not api_key:
            api_key = settings.OPENAI_API_KEY
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url or settings.OPENAI_BASE_URL,
            default_headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        )
        self.model = model or settings.WHISPER_MODEL

    # Mapping from Whisper's returned language names to ISO-639-1 codes
    # This is needed because Whisper returns full names (e.g., "chinese") but expects codes (e.g., "zh")
    LANGUAGE_NAME_TO_CODE = {
        "english": "en",
        "chinese": "zh",
        "german": "de",
        "spanish": "es",
        "russian": "ru",
        "korean": "ko",
        "french": "fr",
        "japanese": "ja",
        "portuguese": "pt",
        "turkish": "tr",
        "polish": "pl",
        "catalan": "ca",
        "dutch": "nl",
        "arabic": "ar",
        "swedish": "sv",
        "italian": "it",
        "indonesian": "id",
        "hindi": "hi",
        "finnish": "fi",
        "vietnamese": "vi",
        "hebrew": "he",
        "ukrainian": "uk",
        "greek": "el",
        "malay": "ms",
        "czech": "cs",
        "romanian": "ro",
        "danish": "da",
        "hungarian": "hu",
        "tamil": "ta",
        "norwegian": "no",
        "thai": "th",
        "urdu": "ur",
        "croatian": "hr",
        "bulgarian": "bg",
        "lithuanian": "lt",
        "latin": "la",
        "maori": "mi",
        "malayalam": "ml",
        "welsh": "cy",
        "slovak": "sk",
        "telugu": "te",
        "persian": "fa",
        "latvian": "lv",
        "bengali": "bn",
        "serbian": "sr",
        "azerbaijani": "az",
        "slovenian": "sl",
        "kannada": "kn",
        "estonian": "et",
        "macedonian": "mk",
        "breton": "br",
        "basque": "eu",
        "icelandic": "is",
        "armenian": "hy",
        "nepali": "ne",
        "mongolian": "mn",
        "bosnian": "bs",
        "kazakh": "kk",
        "albanian": "sq",
        "swahili": "sw",
        "galician": "gl",
        "marathi": "mr",
        "punjabi": "pa",
        "sinhala": "si",
        "khmer": "km",
        "shona": "sn",
        "yoruba": "yo",
        "somali": "so",
        "afrikaans": "af",
        "occitan": "oc",
        "georgian": "ka",
        "belarusian": "be",
        "tajik": "tg",
        "sindhi": "sd",
        "gujarati": "gu",
        "amharic": "am",
        "yiddish": "yi",
        "lao": "lo",
        "uzbek": "uz",
        "faroese": "fo",
        "haitian creole": "ht",
        "pashto": "ps",
        "turkmen": "tk",
        "nynorsk": "nn",
        "maltese": "mt",
        "sanskrit": "sa",
        "luxembourgish": "lb",
        "myanmar": "my",
        "tibetan": "bo",
        "tagalog": "tl",
        "malagasy": "mg",
        "assamese": "as",
        "tatar": "tt",
        "hawaiian": "haw",
        "lingala": "ln",
        "hausa": "ha",
        "bashkir": "ba",
        "javanese": "jw",
        "sundanese": "su",
        "cantonese": "yue",
    }

    def transcribe(self, audio_path: str, language: str = None) -> List[Dict[str, Any]]:
        """
        Transcribes audio file using OpenAI Whisper API.
        Handles large files by chunking them into smaller segments (10 minutes).
        If language is None, Whisper API auto-detects.
        """
        # Normalize language input
        if language:
            language = language.lower().strip()
            if language == 'auto':
                language = None
            else:
                # If the user provided a full name (e.g., 'Chinese'), map it to code
                # Otherwise, keep it as is (assuming it's already an ISO code)
                language = self.LANGUAGE_NAME_TO_CODE.get(language, language)

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
                    # If language is None, Whisper will auto-detect on the first chunk
                    # We can then reuse that language for subsequent chunks to ensure consistency
                    
                    # Prepare language parameter
                    lang_param = language
                    if not lang_param and detected_language:
                        # Map full name to code if detected
                        lang_param = self.LANGUAGE_NAME_TO_CODE.get(detected_language.lower(), detected_language)
                    
                    print(f"[Whisper] Transcribing chunk {i+1}/{chunks_count} ({os.path.basename(chunk_filename)})...")
                    transcript = self.client.audio.transcriptions.create(
                        model=self.model,
                        file=audio_file,
                        response_format="verbose_json",
                        language=lang_param
                    )
                    print(f"[Whisper] Completed chunk {i+1}. Segments found: {len(getattr(transcript, 'segments', []))}")

                # Capture detected language from the first chunk
                if i == 0 and not language:
                    detected_language = getattr(transcript, 'language', None)
                    print(f"Auto-detected language: {detected_language}")

                time_offset_s = start_ms / 1000.0
                
                if hasattr(transcript, 'segments'):
                    for seg in transcript.segments:
                        # Check if it's a dict (e.g. from whisper dict response) or object (Pydantic model)
                        if isinstance(seg, dict):
                            start = seg.get('start', 0)
                            end = seg.get('end', 0)
                            text = seg.get('text', "")
                        else:
                            # Assertive access for object, default to 0/empty if somehow missing
                            start = getattr(seg, 'start', 0)
                            end = getattr(seg, 'end', 0)
                            text = getattr(seg, 'text', "")
                        
                        all_segments.append({
                            "start": start + time_offset_s,
                            "end": end + time_offset_s,
                            "text": text.strip(),
                            "speaker": None # Reserved for Feature 1 (Diarization)
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

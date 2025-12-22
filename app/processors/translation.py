from typing import List, Dict, Any
from openai import OpenAI
from app.config import settings

class TranslationService:
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        if not api_key:
            api_key = settings.OPENAI_API_KEY
            
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url or settings.OPENAI_BASE_URL,
            default_headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        )
        self.model = model or settings.LLM_MODEL

    def translate(self, segments: List[Dict[str, Any]], source_lang: str, target_lang: str) -> List[Dict[str, Any]]:
        """
        Translates a list of transcript segments while preserving structure.
        """
        translated_segments = []
        
        # System prompt with speaker awareness
        system_prompt = (
            f"You are a professional subtitle translator. Translate text from {source_lang} to {target_lang}. "
            "Keep the translation concise and natural for subtitles. "
            "If speaker information is provided as [Speaker X], preserve the context but translate the content. "
            "Output ONLY the translation."
        )

        for segment in segments:
            text = segment['text']
            speaker = segment.get('speaker')
            input_text = f"[{speaker}] {text}" if speaker else text
            
            print(f"[LLM] Translating segment: {input_text[:50]}...")
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": input_text}
                    ],
                    temperature=0.3
                )
                translation = response.choices[0].message.content.strip()
                print(f"[LLM] Result: {translation[:50]}...")
                
                # Strip speaker from translation if LLM included it by mistake
                if speaker and translation.startswith(f"[{speaker}]"):
                    translation = translation[len(f"[{speaker}]"):].strip()
                    if translation.startswith(":"): # Handle "[Speaker 1]: content"
                        translation = translation[1:].strip()
                
                translated_segments.append({
                    "start": segment['start'],
                    "end": segment['end'],
                    "text": translation,
                    "original": text,
                    "speaker": speaker
                })
                
            except Exception as e:
                print(f"Translation error at {segment['start']}: {e}")
                translated_segments.append({
                    "start": segment['start'],
                    "end": segment['end'],
                    "text": f"[Error] {text}",
                    "original": text,
                    "speaker": speaker
                })

        return translated_segments

    def quality_check(self, segments: List[Dict[str, Any]], source_lang: str, target_lang: str) -> List[Dict[str, Any]]:
        """
        Performs a second pass to verify and correct translations.
        """
        system_prompt = (
            f"You are a quality assurance editor for subtitles. Verify the following translations from {source_lang} to {target_lang}. "
            "Correct any hallucinations, awkward phrasing, or mistranslations. "
            "Maintain the same number of segments and order. Output ONLY the corrected text for each segment, separated by '---'."
        )
        
        # Batch processing for efficiency
        batch_size = 10
        for i in range(0, len(segments), batch_size):
            batch = segments[i:i+batch_size]
            prompt_content = "\n".join([f"Orig: {s['original']}\nTrans: {s['text']}\n---" for s in batch])
            
            print(f"[LLM] Running quality check batch for {len(batch)} segments...")
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt_content}
                    ],
                    temperature=0.1
                )
                corrections = [c.strip() for c in response.choices[0].message.content.split('---') if c.strip()]
                print(f"[LLM] Received {len(corrections)} corrections.")
                
                for j, correction in enumerate(corrections):
                    if j < len(batch):
                        batch[j]['text'] = correction
            except Exception as e:
                print(f"Quality check error: {e}")
                
        return segments

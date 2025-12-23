from typing import List, Dict, Any
from openai import OpenAI
import os
import sys
from app.config import settings

def _fix_cuda_paths():
    """
    Helper to find and add NVIDIA DLLs to the PATH on Windows.
    Useful for llama-cpp-python and other C-based GPU libraries.
    """
    if sys.platform != "win32":
        return

    import site
    packages_dirs = site.getsitepackages()
    if hasattr(site, "getusersitepackages"):
        packages_dirs.append(site.getusersitepackages())
    nvidia_dirs = ["nvidia/cudnn/bin", "nvidia/cublas/bin", "nvidia/cuda_runtime/bin"]
    
    for base in packages_dirs:
        for ndir in nvidia_dirs:
            full_path = os.path.join(base, ndir)
            if os.path.exists(full_path):
                os.environ["PATH"] = full_path + os.pathsep + os.environ["PATH"]
                if hasattr(os, "add_dll_directory"):
                    try:
                        os.add_dll_directory(full_path)
                    except Exception: pass

class TranslationService:
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None, local_file: str = None, use_local: bool = False):
        self.use_local = use_local
        self.model = model or (settings.LOCAL_LLM_MODEL if use_local else settings.LLM_MODEL)
        self.local_file = local_file or settings.LOCAL_LLM_FILE
        
        if self.use_local:
            _fix_cuda_paths()
            print(f"[Translation] Initializing Local LLM: {self.model}")
            try:
                from llama_cpp import Llama
                from huggingface_hub import hf_hub_download
            except ImportError:
                raise ImportError("Please install llama-cpp-python and huggingface_hub to use local translation.")

            # Check if model exists locally, if not download
            model_path = os.path.join(settings.MODELS_DIR, self.local_file)
            if not os.path.exists(model_path):
                print(f"[Translation] Model not found at {model_path}. Downloading from HuggingFace...")
                repo_id = self.model
                filename = self.local_file
                try:
                    model_path = hf_hub_download(repo_id=repo_id, filename=filename, local_dir=settings.MODELS_DIR)
                    print(f"[Translation] Model downloaded to {model_path}")
                except Exception as e:
                    raise RuntimeError(f"Failed to download model: {e}")
            
            # Initialize Llama
            # n_gpu_layers=-1 attempts to offload all layers to GPU
            try:
                self.local_client = Llama(
                    model_path=model_path,
                    n_gpu_layers=-1, 
                    n_ctx=4096, # Context window
                    verbose=True
                )
            except Exception as e:
                print(f"[Translation] Error loading local LLM: {e}")
                raise RuntimeError(f"Failed to load local LLM: {e}")
                
        else:
            if not api_key:
                api_key = settings.OPENAI_API_KEY
                
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url or settings.OPENAI_BASE_URL,
                default_headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            )

    def _clean_translation(self, text: str, source_text: str = None) -> str:
        """
        Cleans the LLM output by removing common hallucinations, 
        labels (Original:, Translated:), or accidental source text.
        """
        import re
        
        # Remove common labels
        prefixes = [
            r"^(Translation|Translated|Result|English|Output):\s*",
            r"^(Orig|Original|Src|Source):\s*.*?(?=(Translation|Translated|Result|English|Output|$))",
        ]
        
        cleaned = text.strip()
        for pattern in prefixes:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()
            
        # If the LLM returned "Source: [text] Transition: [translation]", 
        # the previous regex might leave artifacts.
        # Let's handle "Orig: ABC \n Trans: XYZ" specifically
        if "\n" in cleaned:
            lines = [l.strip() for l in cleaned.split("\n") if l.strip()]
            if len(lines) > 1:
                # Look for lines that look like a translation
                trans_lines = [l for l in lines if not any(p in l.lower() for p in ["orig:", "source:", "original:"])]
                if trans_lines:
                    cleaned = " ".join(trans_lines)

        # Final check: if it still has labels like "English: ", strip them
        cleaned = re.sub(r"^\w+:\s*", "", cleaned).strip()
        
        return cleaned

    def _get_completion(self, messages: List[Dict[str, str]], temperature: float = 0.3) -> str:
        """
        Abstracts the chat completion call for both API and Local.
        """
        if self.use_local:
            response = self.local_client.create_chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=None # Let model decide, or set reasonable limit
            )
            return response['choices'][0]['message']['content'].strip()
        else:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature
            )
            return response.choices[0].message.content.strip()

    def translate(self, segments: List[Dict[str, Any]], source_lang: str, target_lang: str) -> List[Dict[str, Any]]:
        """
        Translates a list of transcript segments while preserving structure.
        """
        import time
        translated_segments = []
        total_segments = len(segments)
        
        print(f"[Translation] Starting translation of {total_segments} segments from {source_lang} to {target_lang}")
        
        # System prompt with localization focus
        system_prompt = (
            f"You are a professional subtitle translator and localization expert. "
            f"Translate text from {source_lang} to {target_lang}. "
            "PRIORITY: Focus on conveying the intended meaning, tone, and context rather than a literal word-for-word translation. "
            "The output must be natural, idiomatic English (or the target language) suitable for subtitles. "
            "Approximate the sentence structure to best fit the context of the conversation. "
            "If speaker information is provided as [Speaker X], preserve the context but translate ONLY the content. "
            "RESTRICTION: Output ONLY the final translation. Do not include labels, source text, or explanations."
        )

        for i, segment in enumerate(segments):
            text = segment['text']
            speaker = segment.get('speaker')
            input_text = f"[{speaker}] {text}" if speaker else text
            
            idx = i + 1
            start_time = time.time()
            print(f"[LLM] [{idx}/{total_segments}] Inference started: {input_text[:50]}...")
            
            try:
                translation = self._get_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": input_text}
                    ],
                    temperature=0.3
                )
                
                # Clean the translation
                translation = self._clean_translation(translation, text)
                
                duration = time.time() - start_time
                print(f"[LLM] [{idx}/{total_segments}] Completed in {duration:.2f}s. Result: {translation[:50]}...")
                
                # Strip speaker from translation if LLM included it by mistake
                if speaker and translation.startswith(f"[{speaker}]"):
                    translation = translation[len(f"[{speaker}]"):].strip()
                    if translation.startswith(":"): # Handle "[Speaker 1]: content"
                        translation = translation[1:].strip()
                
                # Final polish cleanup
                translation = self._clean_translation(translation)
                
                translated_segments.append({
                    "start": segment['start'],
                    "end": segment['end'],
                    "text": translation,
                    "original": text,
                    "speaker": speaker
                })
                
            except Exception as e:
                duration = time.time() - start_time
                print(f"[LLM] [{idx}/{total_segments}] Error after {duration:.2f}s: {e}")
                translated_segments.append({
                    "start": segment['start'],
                    "end": segment['end'],
                    "text": f"[Error] {text}",
                    "original": text,
                    "speaker": speaker
                })

        print(f"[Translation] Finished translating {total_segments} segments.")
        return translated_segments

    def quality_check(self, segments: List[Dict[str, Any]], source_lang: str, target_lang: str) -> List[Dict[str, Any]]:
        """
        Performs a second pass to verify and correct translations.
        """
        import time
        system_prompt = (
            f"You are a quality assurance localization editor for subtitles. Verify the following translations from {source_lang} to {target_lang}. "
            "Ensure the translations convey the correct meaning and flow naturally in the target language. "
            "Correct any awkward phrasing, hallucinations, or literal translations that don't make sense. "
            "Maintain the same number of segments and order. Output ONLY the corrected text for each segment, separated by '---'. "
            "RESTRICTION: Do not include labels like 'Orig:' or 'Trans:' in your response."
        )
        
        # Batch processing for efficiency
        batch_size = 10
        total_batches = (len(segments) + batch_size - 1) // batch_size
        
        print(f"[QA] Starting quality check pass for {len(segments)} segments ({total_batches} batches).")

        for i in range(0, len(segments), batch_size):
            batch_idx = (i // batch_size) + 1
            batch = segments[i:i+batch_size]
            prompt_content = "\n".join([f"Orig: {s['original']}\nTrans: {s['text']}\n---" for s in batch])
            
            start_time = time.time()
            print(f"[QA] [{batch_idx}/{total_batches}] Processing batch of {len(batch)} segments...")
            try:
                content = self._get_completion(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt_content}
                    ],
                    temperature=0.1
                )
                
                duration = time.time() - start_time
                corrections = [c.strip() for c in content.split('---') if c.strip()]
                print(f"[QA] [{batch_idx}/{total_batches}] Batch completed in {duration:.2f}s. Received {len(corrections)} segments.")
                
                for j, correction in enumerate(corrections):
                    if j < len(batch):
                        batch[j]['text'] = self._clean_translation(correction)
            except Exception as e:
                duration = time.time() - start_time
                print(f"[QA] [{batch_idx}/{total_batches}] Error after {duration:.2f}s: {e}")
                
        print("[QA] Quality check pass finished.")
        return segments

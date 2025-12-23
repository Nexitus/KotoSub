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
        Includes exponential backoff for API providers.
        """
        import time
        import random

        if self.use_local:
            response = self.local_client.create_chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=None # Let model decide, or set reasonable limit
            )
            return response['choices'][0]['message']['content'].strip()
        else:
            max_retries = 5
            base_delay = 2
            
            for attempt in range(max_retries):
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=temperature
                    )
                    return response.choices[0].message.content.strip()
                except Exception as e:
                    # Check if it's a rate limit error (429)
                    is_rate_limit = "429" in str(e) or "rate_limit" in str(e).lower()
                    
                    if attempt < max_retries - 1:
                        # Exponential backoff with jitter
                        delay = (base_delay ** attempt) + random.uniform(0, 1)
                        if is_rate_limit:
                            delay *= 2 # Wait longer for rate limits
                            
                        # Only print error for non-rate-limit or if it's the 3rd+ attempt
                        if not is_rate_limit or attempt > 1:
                            print(f"[LLM] Connection issue (attempt {attempt+1}/{max_retries}). Retrying in {delay:.1f}s...")
                            
                        time.sleep(delay)
                    else:
                        print(f"[LLM] Final attempt failed: {e}")
                        raise e

    def translate(self, segments: List[Dict[str, Any]], source_lang: str, target_lang: str) -> List[Dict[str, Any]]:
        """
        Translates a list of transcript segments while preserving structure.
        Uses parallel processing for API providers.
        """
        import time
        from concurrent.futures import ThreadPoolExecutor
        from tqdm import tqdm
        import threading

        total_segments = len(segments)
        print(f"[Translation] Starting parallel translation of {total_segments} segments from {source_lang} to {target_lang}")
        
        system_prompt = (
            f"You are a professional subtitle translator and localization expert. "
            f"Translate text from {source_lang} to {target_lang}. "
            "PRIORITY: Focus on conveying the intended meaning, tone, and context rather than a literal word-for-word translation. "
            "The output must be natural, idiomatic English (or the target language) suitable for subtitles. "
            "Approximate the sentence structure to best fit the context of the conversation. "
            "If speaker information is provided as [Speaker X], preserve the context but translate ONLY the content. "
            "RESTRICTION: Output ONLY the final translation. Do not include labels, source text, or explanations."
        )

        results = [None] * total_segments
        # Thread lock for local LLM to prevent concurrent inference which GGUF/llama-cpp doesn't like
        llm_lock = threading.Lock()

        def translate_single(index, segment):
            text = segment['text']
            speaker = segment.get('speaker')
            input_text = f"[{speaker}] {text}" if speaker else text
            
            try:
                # If local, we MUST lock
                if self.use_local:
                    with llm_lock:
                        translation = self._get_completion(
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": input_text}
                            ],
                            temperature=0.3
                        )
                else:
                    translation = self._get_completion(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": input_text}
                        ],
                        temperature=0.3
                    )
                
                # Clean the translation
                translation = self._clean_translation(translation, text)
                
                # Strip speaker from translation if LLM included it by mistake
                if speaker and translation.startswith(f"[{speaker}]"):
                    translation = translation[len(f"[{speaker}]"):].strip()
                    if translation.startswith(":"): # Handle "[Speaker 1]: content"
                        translation = translation[1:].strip()
                
                # Final polish cleanup
                translation = self._clean_translation(translation)
                
                results[index] = {
                    "start": segment['start'],
                    "end": segment['end'],
                    "text": translation,
                    "original": text,
                    "speaker": speaker
                }
            except Exception as e:
                # print(f"[LLM] Error at index {index}: {e}") # Suppress to keep tqdm clean
                results[index] = {
                    "start": segment['start'],
                    "end": segment['end'],
                    "text": f"[Error] {text}",
                    "original": text,
                    "speaker": speaker
                }

        # Use more workers for API, fewer for local to avoid overhead
        max_workers = 10 if not self.use_local else 2
        
        with tqdm(total=total_segments, desc="Translating", unit="seg", colour="green") as pbar:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for i, seg in enumerate(segments):
                    future = executor.submit(translate_single, i, seg)
                    future.add_done_callback(lambda _: pbar.update(1))
                    futures.append(future)
                
                # Wait for all to complete
                for future in futures:
                    future.result()

        print(f"[Translation] Finished translating {total_segments} segments.")
        return [r for r in results if r is not None]

    def quality_check(self, segments: List[Dict[str, Any]], source_lang: str, target_lang: str) -> List[Dict[str, Any]]:
        """
        Performs a second pass to verify and fix translation quality.
        Uses parallel processing for API providers.
        """
        from concurrent.futures import ThreadPoolExecutor
        from tqdm import tqdm
        import threading

        total_segments = len(segments)
        print(f"[QA] Starting parallel quality verification for {total_segments} segments...")
        
        system_prompt = (
            f"You are a subtitle localization auditor. You will be given a target translation ({target_lang}) "
            f"and the original source text ({source_lang}). "
            "Your job is to fix any errors, hallucinations, or unnatural phrasing. "
            "Ensure the translation is idiomatic and preserves the emotional tone and context of the original. "
            "If the translation is already perfect, return it unchanged. "
            "RESTRICTION: Output ONLY the improved text. No labels or explanations."
        )

        results = [None] * total_segments
        llm_lock = threading.Lock()

        def qa_single(index, segment):
            original = segment.get('original', segment['text'])
            translated = segment['text']
            
            user_content = f"Original: {original}\nTranslated: {translated}"
            
            try:
                if self.use_local:
                    with llm_lock:
                        refined = self._get_completion(
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_content}
                            ],
                            temperature=0.2
                        )
                else:
                    refined = self._get_completion(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content}
                        ],
                        temperature=0.2
                    )
                
                # Cleanup
                refined = self._clean_translation(refined, original)
                
                new_segment = segment.copy()
                new_segment['text'] = refined
                results[index] = new_segment
            except Exception:
                results[index] = segment # Fallback to unrefined

        max_workers = 10 if not self.use_local else 2
        
        with tqdm(total=total_segments, desc="Verifying", unit="seg", colour="yellow") as pbar:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                for i, seg in enumerate(segments):
                    future = executor.submit(qa_single, i, seg)
                    future.add_done_callback(lambda _: pbar.update(1))
                    futures.append(future)
                
                for future in futures:
                    future.result()

        print("[QA] Quality verification complete.")
        return [r for r in results if r is not None]

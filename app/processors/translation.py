from typing import List, Dict, Any
import os
from app.cuda import fix_cuda_paths
from app.config import settings
from app.processors.subtitles import is_cjk_char

class TranslationService:
    # Sugoi models are trained/tuned for a ~2048 token context window.
    MODEL_N_CTX_OVERRIDES = {
        "DharkNet3/Sugoi-32B-Ultra-IQ3_M-GGUF": 2048,
    }

    def __init__(self, model: str = None, local_file: str = None):
        self.model = model or settings.LOCAL_LLM_MODEL
        self.local_file = local_file or settings.LOCAL_LLM_FILE
        fix_cuda_paths()
        print(f"[Translation] Initializing Local LLM: {self.model}")
        try:
            from llama_cpp import Llama
            from huggingface_hub import hf_hub_download
        except ImportError:
            raise ImportError("Please install llama-cpp-python and huggingface_hub to use local translation.")

        model_path = os.path.join(settings.MODELS_DIR, self.local_file)
        if not os.path.exists(model_path):
            print(f"[Translation] Model not found at {model_path}. Downloading from HuggingFace...")
            try:
                model_path = hf_hub_download(repo_id=self.model, filename=self.local_file, local_dir=settings.MODELS_DIR)
                print(f"[Translation] Model downloaded to {model_path}")
            except Exception as e:
                raise RuntimeError(f"Failed to download model: {e}")

        n_ctx = self.MODEL_N_CTX_OVERRIDES.get(self.model, settings.LLM_N_CTX)
        try:
            self.local_client = Llama(
                model_path=model_path,
                n_gpu_layers=-1,
                n_ctx=n_ctx,
                n_batch=settings.LLM_N_BATCH,
                n_threads=settings.LLM_N_THREADS,
                flash_attn=settings.LLM_FLASH_ATTN,
                verbose=True
            )
        except Exception as e:
            print(f"[Translation] Error loading local LLM: {e}")
            raise RuntimeError(f"Failed to load local LLM: {e}")

        # chat_template_kwargs was added in a later version of llama-cpp-python.
        # Introspect once instead of on every completion call.
        self._chat_template_ok = False
        try:
            import inspect
            self._chat_template_ok = ("chat_template_kwargs" in
                inspect.signature(self.local_client.create_chat_completion).parameters)
        except Exception:
            pass

    def _clean_translation(self, text: str, source_text: str = None) -> str:
        import re

        prefixes = [
            r"^(Translation|Translated|Result|English|Output):\s*",
            r"^(Orig|Original|Src|Source):\s*.*?(?=(Translation|Translated|Result|English|Output|$))",
        ]

        cleaned = text.strip()

        # Remove chain-of-thought reasoning tags (Qwen 3 and similar models)
        cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r'<thinking>.*?</thinking>', '', cleaned, flags=re.IGNORECASE | re.DOTALL)

        for pattern in prefixes:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE | re.DOTALL).strip()

        blacklist = [
            r"amara\.org", r"subtitle(s)? by", r"translated by", r"edited by",
            r"proofread by", r"corrected by", r"captioned by", r"sync(hronized)? by",
            r"brought to you by", r"support us at", r"osdb\.link",
            r"opensubtitles", r"titlovi\.com", r"podnapisi\.net",
        ]

        for pattern in blacklist:
            lines = cleaned.split("\n")
            cleaned = "\n".join(l for l in lines if not re.search(pattern, l, re.IGNORECASE)).strip()

        if "\n" in cleaned:
            lines = [l.strip() for l in cleaned.split("\n") if l.strip()]
            if len(lines) > 1:
                trans_lines = [l for l in lines if not any(p in l.lower() for p in ["orig:", "source:", "original:"])]
                if trans_lines:
                    cleaned = " ".join(trans_lines)

        cleaned = re.sub(r"^\w+:\s*", "", cleaned).strip()
        return cleaned

    @staticmethod
    def _has_cjk(text: str) -> bool:
        return any(is_cjk_char(ch) for ch in text)

    def _parse_numbered_lines(self, completion: str, expected: int):
        """Parses 'N. text' lines from a completion. Returns a list of exactly
        `expected` strings, or None if the response is unusable."""
        lines = completion.split("\n")
        translations = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if ". " in line:
                parts = line.split(". ", 1)
                if parts[0].isdigit():
                    translations.append(parts[1].strip())
            elif line[0].isdigit() and len(line) > 1:
                for k, char in enumerate(line):
                    if not char.isdigit():
                        translations.append(line[k:].lstrip(" .:;，,)）］】]").strip())
                        break

        if len(translations) == expected:
            return translations

        raw_lines = [l for l in lines if l.strip()]
        if len(raw_lines) == expected:
            return [l.split(". ", 1)[-1] if ". " in l else l for l in raw_lines]
        return None

    def _translate_lines(self, batch_segments: List[Dict[str, Any]],
                         source_lang: str, target_lang: str,
                         context: List[tuple], temperature: float = None):
        """Translates one numbered batch. Returns a list of translations or
        None if the model returned an unparseable / mismatched response."""
        if temperature is None:
            temperature = settings.LLM_TRANSLATE_TEMPERATURE
        system_prompt = (
            f"You are a professional subtitle translator and localization expert. "
            f"Translate text from {source_lang} to {target_lang}. "
            "PRIORITY: Focus on conveying the intended meaning, tone, and context. "
            "The output must be natural, idiomatic and suitable for subtitles. "
            "RESTRICTION: Do NOT include any meta-talk, watermarks (e.g., amara.org), "
            "credits, or AI labels. Do NOT repeat the input. "
            "Do NOT use thinking tags like <think> or chain-of-thought reasoning. "
            "Do NOT include any thinking or reasoning before the answer. "
            "Output ONLY the final translated text. "
            "PROTOCOL: You will receive numbered lines. Return exactly the same number "
            "of numbered lines, one translation per input line, in the same order. "
            "Keep names, terminology, pronouns and tone consistent with the context lines. "
            "Format: Number. [Translated Text]"
        )

        parts = []
        if context:
            parts.append("Context (previous lines, already translated — reference only, do NOT re-translate):")
            for src, tgt in context:
                parts.append(f"{src} => {tgt}")
            parts.append("")
        parts.append(f"Translate these {len(batch_segments)} numbered lines:")
        for i, seg in enumerate(batch_segments):
            text = seg['text']
            speaker = seg.get('speaker')
            prefix = f"[{speaker}] " if speaker else ""
            parts.append(f"{i+1}. {prefix}{text}")

        try:
            completion = self._get_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "\n".join(parts)}
                ],
                temperature=temperature
            )
        except Exception as e:
            print(f"[Translation] Batch call failed: {type(e).__name__}: {e}")
            return None

        return self._parse_numbered_lines(completion, len(batch_segments))

    def _translate_lines_retried(self, batch_segments: List[Dict[str, Any]],
                                 source_lang: str, target_lang: str,
                                 context: List[tuple]) -> List[str]:
        """Retries a failed batch by splitting it in halves until single lines.
        Single-line failures fall back to an error marker."""
        if len(batch_segments) == 1:
            return [f"[Error] {batch_segments[0]['text']}"]
        mid = len(batch_segments) // 2
        out = []
        for half in (batch_segments[:mid], batch_segments[mid:]):
            result = self._translate_lines(half, source_lang, target_lang, context)
            if result is None:
                out.extend(self._translate_lines_retried(half, source_lang, target_lang, context))
            else:
                out.extend(result)
        return out

    def _get_completion(self, messages: List[Dict[str, str]], temperature: float = 0.3) -> str:
        kwargs = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": None,
            "frequency_penalty": settings.LLM_FREQUENCY_PENALTY,
            "presence_penalty": settings.LLM_PRESENCE_PENALTY,
        }
        if self._chat_template_ok:
            kwargs["chat_template_kwargs"] = {"enable_thinking": False}

        response = self.local_client.create_chat_completion(**kwargs)
        return response['choices'][0]['message']['content'].strip()

    def translate(self, segments: List[Dict[str, Any]], source_lang: str, target_lang: str,
                  segment_callback=None) -> List[Dict[str, Any]]:
        from tqdm import tqdm

        total_segments = len(segments)
        batch_size = max(1, settings.LLM_TRANSLATE_BATCH)
        print(f"[Translation] Starting translation of {total_segments} segments from {source_lang} to {target_lang} "
              f"(batch size {batch_size}, {settings.LLM_CONTEXT_LINES} context lines)")

        results = []
        context: List[tuple] = []

        with tqdm(total=total_segments, desc="Translating", unit="seg", colour="green") as pbar:
            for batch_start in range(0, total_segments, batch_size):
                batch = segments[batch_start:batch_start + batch_size]

                translations = self._translate_lines(batch, source_lang, target_lang, context)
                if translations is None:
                    print(f"[Translation] Batch at {batch_start} returned mismatched lines, retrying in halves...")
                    translations = self._translate_lines_retried(batch, source_lang, target_lang, context)

                for seg, trans in zip(batch, translations):
                    error = trans.startswith("[Error")
                    cleaned = trans if error else self._clean_translation(trans, seg['text'])
                    results.append({
                        "start": seg['start'],
                        "end": seg['end'],
                        "text": cleaned,
                        "original": seg['text'],
                        "speaker": seg.get('speaker'),
                        "words": seg.get('words'),
                        "avg_logprob": seg.get('avg_logprob')
                    })
                    pbar.update(1)
                    if segment_callback:
                        segment_callback(results[-1])
                    # Rolling context of recent (source, translation) pairs
                    if not error:
                        context.append((seg['text'], cleaned))
                context = context[-settings.LLM_CONTEXT_LINES:]

        print(f"[Translation] Finished translating {total_segments} segments.")
        return results

    def translate_chunk(self, segments: List[Dict[str, Any]],
                        source_lang: str, target_lang: str,
                        context: List[tuple] = None) -> List[Dict[str, Any]]:
        print(f"[Translation] Chunk: translating {len(segments)} segments"
              + (f" ({len(context)} context lines)" if context else ""))

        try:
            translations = self._translate_lines(segments, source_lang, target_lang, context or [])
            if translations is None:
                translations = [f"[Error: Count mismatch] {s['text']}" for s in segments]
        except Exception as e:
            print(f"[Translation] Chunk failed: {type(e).__name__}: {e}")
            translations = [f"[Error] {s['text']}" for s in segments]

        results = []
        for seg, trans in zip(segments, translations):
            cleaned = trans if trans.startswith("[Error") else self._clean_translation(trans, seg['text'])
            results.append({
                "start": seg['start'],
                "end": seg['end'],
                "text": cleaned,
                "original": seg['text'],
                "speaker": seg.get('speaker'),
                "words": seg.get('words'),
                "avg_logprob": seg.get('avg_logprob')
            })
        return results

    def _is_suspect(self, segment: Dict[str, Any]) -> bool:
        """Heuristic check for segments that need a second look."""
        text = (segment.get('text') or '').strip()
        original = (segment.get('original') or '').strip()

        if not text:
            return True
        if text.startswith("[Error"):
            return True
        # Untranslated: output identical to a CJK source (no script conversion happened)
        if original and text == original and self._has_cjk(original):
            return True
        # Low-confidence source transcript (from Whisper avg_logprob)
        logprob = segment.get('avg_logprob')
        if logprob is not None and logprob < settings.WHISPER_RETRY_LOGPROB:
            return True
        # Suspiciously short compared to the source
        if original and len(text) < max(1, len(original) * 0.15):
            return True
        return False

    def _comet_scores(self, segments: List[Dict[str, Any]]) -> List[float]:
        """Optional COMETKiwi quality estimation. Returns per-segment scores in
        [0, 1] (higher is better), or None when the comet package / model is
        unavailable — everything then falls back to heuristics only."""
        if not settings.QA_USE_COMET:
            return None
        try:
            from comet import download_model, load_from_checkpoint
            import torch
        except ImportError:
            print("[QA] comet package not installed — using heuristic suspect detection only.")
            return None

        try:
            model_path = download_model("Unbabel/wmt22-cometkiwi-da")
            model = load_from_checkpoint(model_path)
            data = [{"src": (s.get('original') or ''), "mt": (s.get('text') or '')} for s in segments]
            gpus = 1 if torch.cuda.is_available() else 0
            _, scores = model.predict(data, batch_size=32, gpus=gpus, progress_bar=False)
            return list(scores)
        except Exception as e:
            print(f"[QA] COMETKiwi unavailable ({type(e).__name__}: {e}) — using heuristics only.")
            return None

    def quality_check(self, segments: List[Dict[str, Any]], source_lang: str, target_lang: str) -> List[Dict[str, Any]]:
        from tqdm import tqdm

        total_segments = len(segments)
        print(f"[QA] Starting quality verification for {total_segments} segments...")

        # Targeted QA: only re-check suspect segments instead of re-running the
        # LLM over the whole transcript. Suspects = heuristic flags + (optional)
        # low COMETKiwi scores.
        suspect_flags = [self._is_suspect(seg) for seg in segments]
        comet_scores = self._comet_scores(segments)
        if comet_scores is not None and len(comet_scores) == total_segments:
            for i, score in enumerate(comet_scores):
                if score < settings.QA_COMET_THRESHOLD:
                    suspect_flags[i] = True

        suspect_indices = [i for i, flag in enumerate(suspect_flags) if flag]
        print(f"[QA] Flagged {len(suspect_indices)}/{total_segments} segments for re-verification"
              + (" (COMETKiwi)" if comet_scores is not None else " (heuristics)"))

        if not suspect_indices:
            print("[QA] No suspect segments found. Skipping verification pass.")
            return segments

        system_prompt = (
            f"You are a subtitle localization auditor. You will be given a target translation ({target_lang}) "
            f"and the original source text ({source_lang}). "
            "Your job is to fix any errors, hallucinations, or unnatural phrasing. "
            "Ensure the translation is idiomatic and preserves the emotional tone and context of the original. "
            "If the translation is already perfect, return it unchanged. "
            "A previous translated line may be provided for continuity — reference it for pronouns and tense, "
            "but do NOT re-translate it. "
            "RESTRICTION: Output ONLY the improved text. No labels, explanations, or watermarks (e.g., amara.org)."
            "Do NOT include credits or AI metadata."
            "Do NOT use thinking tags like <think> or chain-of-thought reasoning."
        )

        results = list(segments)

        with tqdm(total=len(suspect_indices), desc="Verifying", unit="seg", colour="yellow") as pbar:
            for i in suspect_indices:
                segment = segments[i]
                original = segment.get('original', segment['text'])
                user_parts = []
                if i > 0:
                    prev = segments[i - 1]
                    user_parts.append(
                        f"Previous line (context only): {prev.get('original', '')} => {prev.get('text', '')}"
                    )
                user_parts.append(f"Original: {original}\nTranslated: {segment['text']}")
                try:
                    refined = self._get_completion(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": "\n".join(user_parts)}
                        ],
                        temperature=0.2
                    )
                    refined = self._clean_translation(refined, original)
                    if refined:
                        new_segment = segment.copy()
                        new_segment['text'] = refined
                        results[i] = new_segment
                except Exception as e:
                    print(f"[QA] Segment {i} failed: {type(e).__name__}: {e}")
                pbar.update(1)

        print(f"[QA] Quality verification complete ({len(suspect_indices)} segments re-checked).")
        return results

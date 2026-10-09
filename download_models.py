
import os
from huggingface_hub import hf_hub_download
from faster_whisper import WhisperModel

from app.config import settings

MODELS_DIR = settings.MODELS_DIR
os.makedirs(MODELS_DIR, exist_ok=True)

LLM_MODELS = [
    {
        "label": "Sugoi 32B Ultra — Japanese→English Specialist (15 GB VRAM)",
        "repo": "DharkNet3/Sugoi-32B-Ultra-IQ3_M-GGUF",
        "file": "Sugoi-32B-Ultra-IQ3_M.gguf",
        "recommended_for": ["ja"]
    },
    {
        "label": "Translate Gemma 4 Sub E4B — Subtitle Specialist, Default (6 GB VRAM)",
        "repo": "17slever17/translate-gemma-4-sub-e4b-GGUF",
        "file": "translate_gemma4_sub-E4B-Q4_K_XL.gguf",
        "recommended_for": ["*"]
    },
    {
        "label": "Gemma 4 12B QAT — Multilingual Mid-Tier (9 GB VRAM)",
        "repo": "unsloth/gemma-4-12B-it-qat-GGUF",
        "file": "gemma-4-12B-it-qat-UD-Q4_K_XL.gguf"
    },
    {
        "label": "Qwen 3.5 9B — Great Quality / Low VRAM (6 GB VRAM)",
        "repo": "unsloth/Qwen3.5-9B-GGUF",
        "file": "Qwen3.5-9B-Q4_K_M.gguf"
    },
    {
        "label": "Qwen 3.5 4B — Speed Priority (2.5 GB VRAM)",
        "repo": "unsloth/Qwen3.5-4B-GGUF",
        "file": "Qwen3.5-4B-Q4_K_M.gguf"
    },
    {
        "label": "GLM-4 9B — Chinese Specialist (5.5 GB VRAM)",
        "repo": "bartowski/glm-4-9b-chat-GGUF",
        "file": "glm-4-9b-chat-Q4_K_M.gguf",
        "recommended_for": ["zh"]
    },
]

# Recommended LLM per source language ('*' is the fallback for all others)
RECOMMENDED_BY_LANG = {
    "ja": "DharkNet3/Sugoi-32B-Ultra-IQ3_M-GGUF",
    "zh": "bartowski/glm-4-9b-chat-GGUF",
    "*": "17slever17/translate-gemma-4-sub-e4b-GGUF",
}

# Optional quality-estimation model for the targeted QA pass is downloaded
# by comet itself on first use (gated: accept the license on HuggingFace).

WHISPER_MODELS = ["medium", "large-v3", "large-v3-turbo", "distil-whisper/distil-large-v3.5-ct2"]

# Alternative transcription engine (optional dependency: `pip install qwen-asr`).
# Whisper stays the default; this is offered in the same transcription selector.
QWEN_ASR = {
    "label": "Qwen3-ASR 1.7B — Alternative (Word Timestamps, ~5 GB total)",
    "value": "Qwen/Qwen3-ASR-1.7B",
    "asr_repo": "Qwen/Qwen3-ASR-1.7B",
    "aligner_repo": "Qwen/Qwen3-ForcedAligner-0.6B",
}
QWEN_ASR_CACHES = ("models--Qwen--Qwen3-ASR-1.7B", "models--Qwen--Qwen3-ForcedAligner-0.6B")


def _hf_cache_dir():
    from huggingface_hub.constants import HF_HUB_CACHE
    return HF_HUB_CACHE


def qwen_asr_installed() -> bool:
    """Installed when both repos have a downloaded snapshot in the HF cache
    (qwen-asr loads from_pretrained directly from the hub cache; on first use
    it downloads on demand, same behavior as faster-whisper's cache)."""
    try:
        cache_dir = _hf_cache_dir()
    except Exception:
        return False
    for cache_name in QWEN_ASR_CACHES:
        snapshots = os.path.join(cache_dir, cache_name, "snapshots")
        if not (os.path.isdir(snapshots) and _has_snapshot(snapshots)):
            return False
    return True


def _has_snapshot(snapshots: str) -> bool:
    try:
        return any(os.scandir(snapshots))
    except OSError:
        return False


def download_qwen_asr_model(force=False):
    """Downloads the Qwen3-ASR model and its ForcedAligner into the HF cache."""
    if qwen_asr_installed() and not force:
        print(f"[Qwen-ASR] {QWEN_ASR['label']} already exists. Skipping.")
        return True
    from huggingface_hub import snapshot_download
    ok = True
    for repo in (QWEN_ASR["asr_repo"], QWEN_ASR["aligner_repo"]):
        try:
            print(f"[Qwen-ASR] Downloading {repo} ...")
            snapshot_download(repo_id=repo, token=settings.HF_TOKEN,
                              force_download=force)
            print(f"[Qwen-ASR] Downloaded {repo}")
        except Exception as e:
            print(f"[Qwen-ASR] Error downloading {repo}: {e}")
            ok = False
    return ok


def remove_qwen_asr_model():
    """Removes the Qwen3-ASR model + aligner from the HF cache."""
    import shutil
    ok = True
    try:
        cache_dir = _hf_cache_dir()
    except Exception:
        print("[Qwen-ASR] Could not resolve the HuggingFace cache directory.")
        return False
    for cache_name in QWEN_ASR_CACHES:
        repo_dir = os.path.join(cache_dir, cache_name)
        if os.path.isdir(repo_dir):
            try:
                shutil.rmtree(repo_dir)
                print(f"[Qwen-ASR] Removed {cache_name}")
            except Exception as e:
                print(f"[Qwen-ASR] Error removing {cache_name}: {e}")
                ok = False
        else:
            print(f"[Qwen-ASR] {cache_name} is not installed.")
    return ok

def download_llm_model(model, force=False):
    """Downloads a specific LLM model."""
    model_path = os.path.join(MODELS_DIR, model["file"])
    
    if os.path.exists(model_path) and not force:
        print(f"[LLM] {model['label']} already exists. Skipping.")
        return True
    
    print(f"[LLM] Downloading {model['label']} from {model['repo']}...")
    try:
        hf_hub_download(
            repo_id=model["repo"],
            filename=model["file"],
            local_dir=MODELS_DIR,
            token=settings.HF_TOKEN,
            force_download=force
        )
        print(f"[LLM] Successfully downloaded {model['label']}")
        return True
    except Exception as e:
        print(f"[LLM] Error downloading {model['label']}: {e}")
        return False

def remove_llm_model(model):
    """Removes a specific LLM model file."""
    model_path = os.path.join(MODELS_DIR, model["file"])
    if os.path.exists(model_path):
        try:
            os.remove(model_path)
            print(f"[LLM] Removed {model['label']}")
            return True
        except Exception as e:
            print(f"[LLM] Error removing {model['label']}: {e}")
            return False
    return True # Already gone

def download_whisper_model(model_name, force=False):
    """Downloads a specific Whisper model."""
    print(f"[Whisper] Processing {model_name} model...")
    
    # faster-whisper verifies/downloads via its cache on instantiation;
    # load on CPU so this stays safe on machines without a GPU.
    try:
        WhisperModel(
            model_name, 
            device="cpu",
            compute_type="int8", 
            download_root=MODELS_DIR
        )
        print(f"[Whisper] verified/downloaded {model_name}")
        return True
    except Exception as e:
        print(f"[Whisper] Error with {model_name}: {e}")
        return False

def remove_whisper_model(model_name):
    """Removes a specific Whisper model directory."""
    import shutil
    target_dir = None

    cache_name = model_name.replace("/", "--")

    for item in os.listdir(MODELS_DIR):
        if cache_name in item and os.path.isdir(os.path.join(MODELS_DIR, item)):
             target_dir = os.path.join(MODELS_DIR, item)
             break

    if target_dir:
        try:
            shutil.rmtree(target_dir)
            print(f"[Whisper] Removed {model_name} (Deleted {os.path.basename(target_dir)})")
            return True
        except Exception as e:
            print(f"[Whisper] Error removing {target_dir}: {e}")
            return False
    else:
        print(f"[Whisper] Could not find folder for {model_name}")
        return False

def download_llms():
    """Batch download all recommended LLMs."""
    print("\n--- Downloading LLM Models ---")
    for model in LLM_MODELS:
        download_llm_model(model)

def download_whisper():
    """Batch download all recommended Whisper models."""
    print("\n--- Downloading Whisper Models ---")
    for model_name in WHISPER_MODELS:
        download_whisper_model(model_name)

if __name__ == "__main__":
    download_llms()
    download_whisper()
    print("\nAll downloads complete!")


import os
import sys
from huggingface_hub import hf_hub_download
from faster_whisper import WhisperModel
import torch

# Add current directory to path so we can import settings
sys.path.append(os.getcwd())
try:
    from app.config import settings
except ImportError:
    # Fallback if config is not importable
    class MockSettings:
        MODELS_DIR = os.path.join(os.getcwd(), "models")
    settings = MockSettings()

MODELS_DIR = settings.MODELS_DIR
os.makedirs(MODELS_DIR, exist_ok=True)

LLM_MODELS = [
    {
        "label": "Qwen 3 8B (Strong/Chinese-Native)",
        "repo": "Qwen/Qwen3-8B-GGUF",
        "file": "Qwen3-8B-Q4_K_M.gguf"
    },
    {
        "label": "Dolphin 2.8 Mistral (Uncensored)",
        "repo": "mradermacher/dolphin-2.8-mistral-7b-v02-GGUF",
        "file": "dolphin-2.8-mistral-7b-v02.Q4_K_M.gguf"
    },
    {
        "label": "Noromaid 7B v0.4 (Creative/NSFW)",
        "repo": "NeverSleep/Noromaid-7B-0.4-DPO-GGUF",
        "file": "Noromaid-7B-0.4-DPO.q4_k_m.gguf"
    },
    {
        "label": "OpenHermes 2.5 (High Quality/Low Filter)",
        "repo": "TheBloke/OpenHermes-2.5-Mistral-7B-GGUF",
        "file": "openhermes-2.5-mistral-7b.Q4_K_M.gguf"
    },
    {
        "label": "Gemma 2 9B (Google/Fast)",
        "repo": "bartowski/gemma-2-9b-it-GGUF",
        "file": "gemma-2-9b-it-Q4_K_M.gguf"
    }
]

WHISPER_MODELS = ["medium", "large-v3", "large-v3-turbo"]

def download_llm_model(model, force=False):
    """Downloads a specific LLM model."""
    hf_token = os.getenv("HF_TOKEN")
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
            token=hf_token,
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
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    
    # Whisper models are directories in the cache/models dir.
    # Faster-whisper uses a cache. We can try to force download by clearing specific cache if strictly needed,
    # but practically re-instantiating with download_root handles verification.
    
    try:
        # If force is true, we might want to manually clean up, but faster-whisper doesn't strictly support 'force_download' param in init.
        # However, we can use download_model from faster_whisper to be more explicit (if available) or just rely on its check.
        # For simplicity in this context, 'force' might just mean "try to download again over top".
        
        WhisperModel(
            model_name, 
            device="cpu", # Use CPU for download to be safe
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
    # This is tricky because faster-whisper/CTranslate2 names folders with hashes.
    # We might have to scan MODELS_DIR for folders usually named 'models--systran--faster-whisper-...'
    # For now, let's just warn that manual removal might be safest or look for standard patterns if we assume standard HF layout.
    # Actually, faster-whisper with download_root=MODELS_DIR typically creates:
    # MODELS_DIR/models--systran--faster-whisper-{size}/...
    
    # Simple heuristic:
    import shutil
    target_dir = None
    # Common mapped names
    if model_name == "large-v3-turbo":
       possible_name = "models--deepdml--faster-whisper-large-v3-turbo-ct2" # Example, varies by repo source used by lib
       # faster-whisper default is Systran
    
    # To implement robustly we would need to know exact folder name. 
    # For now, we will scan for the model size in the folder name.
    
    for item in os.listdir(MODELS_DIR):
        if "faster-whisper" in item and model_name in item and os.path.isdir(os.path.join(MODELS_DIR, item)):
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

def get_llm_models():
    return LLM_MODELS

def get_whisper_models():
    return WHISPER_MODELS

if __name__ == "__main__":
    download_llms()
    download_whisper()
    print("\nAll downloads complete!")

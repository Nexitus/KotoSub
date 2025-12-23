
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
        "label": "Mistral 7B v0.2 (Balanced)",
        "repo": "TheBloke/Mistral-7B-Instruct-v0.2-GGUF",
        "file": "mistral-7b-instruct-v0.2.Q4_K_M.gguf"
    },
    {
        "label": "Dolphin 2.8 Mistral (Uncensored)",
        "repo": "mradermacher/dolphin-2.8-mistral-7b-v02-GGUF",
        "file": "dolphin-2.8-mistral-7b-v02.Q4_K_M.gguf"
    },
    {
        "label": "Noromaid 7B v0.4 (Creative/NSFW)",
        "repo": "NeverSleep/Noromaid-7B-0.4-DPO-GGUF",
        "file": "Noromaid-7B-0.4-DPO.Q4_K_M.gguf"
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
    },
    {
        "label": "Llama 3 8B (Meta/Strong)",
        "repo": "bartowski/Meta-Llama-3-8B-Instruct-GGUF",
        "file": "Meta-Llama-3-8B-Instruct-Q4_K_M.gguf"
    }
]

WHISPER_MODELS = ["tiny", "base", "small", "medium", "large-v3"]

def download_llms():
    print("\n--- Downloading LLM Models ---")
    hf_token = os.getenv("HF_TOKEN")
    for model in LLM_MODELS:
        model_path = os.path.join(MODELS_DIR, model["file"])
        if os.path.exists(model_path):
            print(f"[LLM] {model['label']} already exists at {model_path}. Skipping.")
            continue
        
        print(f"[LLM] Downloading {model['label']} from {model['repo']}...")
        try:
            hf_hub_download(
                repo_id=model["repo"],
                filename=model["file"],
                local_dir=MODELS_DIR,
                token=hf_token
            )
            print(f"[LLM] Successfully downloaded {model['label']}")
        except Exception as e:
            print(f"[LLM] Error downloading {model['label']}: {e}")

def download_whisper():
    print("\n--- Downloading Whisper Models ---")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    compute_type = "float16" if device == "cuda" else "int8"
    
    for model_name in WHISPER_MODELS:
        print(f"[Whisper] Pre-loading {model_name} model...")
        try:
            # WhisperModel constructor handles download if not present
            WhisperModel(
                model_name, 
                device="cpu", # Download using CPU to avoid memory issues during batch
                compute_type="int8", 
                download_root=MODELS_DIR
            )
            print(f"[Whisper] Successfully pre-loaded {model_name}")
        except Exception as e:
            print(f"[Whisper] Error pre-loading {model_name}: {e}")

if __name__ == "__main__":
    download_llms()
    download_whisper()
    print("\nAll downloads complete!")

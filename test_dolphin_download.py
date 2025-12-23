
import os
from huggingface_hub import hf_hub_download

REPO = "mradermacher/dolphin-2.8-mistral-7b-v02-GGUF"
FILE = "dolphin-2.8-mistral-7b-v02.Q4_K_M.gguf"
DEST = os.path.join(os.getcwd(), "models")

print(f"Targeting: {REPO}/{FILE}")
print(f"Destination: {DEST}")

try:
    path = hf_hub_download(repo_id=REPO, filename=FILE, local_dir=DEST)
    print(f"Success! Model downloaded to: {path}")
except Exception as e:
    print(f"FAILED: {e}")

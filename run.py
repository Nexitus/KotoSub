import sys
import subprocess
import os
import shutil

from app.cuda import fix_cuda_paths

def check_dependencies():
    print("🔍 Checking system dependencies...")
    
    # 1. Check for FFmpeg
    if not shutil.which("ffmpeg"):
        print("❌ Error: FFmpeg not found in system PATH.")
        print("Please install FFmpeg and add it to your PATH to continue.")
        sys.exit(1)
    
    # 2. Check for Python dependencies
    requirements_file = "requirements.txt"
    if os.path.exists(requirements_file):
        try:
            print("📦 Verifying Python packages...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", requirements_file])
            print("✅ Dependencies are up to date.")
        except Exception as e:
            print(f"⚠️ Warning: Automatic dependency installation failed: {e}")
            print("Please run 'pip install -r requirements.txt' manually.")
    
    # 3. Windows Specific: Check for NVIDIA libraries if we expect GPU
    if sys.platform == "win32":
        try:
            import importlib.util
            cudnn_found = importlib.util.find_spec("nvidia.cudnn")
            if not cudnn_found:
                print("💡 Tip: For Local GPU support on Windows, run: pip install nvidia-cudnn-cu12 nvidia-cublas-cu12")
        except Exception:
            pass

def _find_nvcc():
    """Find nvcc.exe by checking CUDA_PATH env var and common install locations."""
    cuda_path = os.environ.get("CUDA_PATH") or os.environ.get("CUDA_HOME")
    if cuda_path:
        nvcc = os.path.join(cuda_path, "bin", "nvcc.exe")
        if os.path.exists(nvcc):
            return nvcc.replace("\\", "/")
    base = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA"
    if os.path.isdir(base):
        for ver in sorted(os.listdir(base), reverse=True):
            nvcc = os.path.join(base, ver, "bin", "nvcc.exe")
            if os.path.exists(nvcc):
                return nvcc.replace("\\", "/")
    return None


def install_ai_packages():
    """
    Install AI packages that need special handling.
    GPU is required — no CPU fallback.
    """
    # --- PyTorch (CUDA required) ---
    cuda_ok = False
    try:
        import torch
        cuda_ok = torch.cuda.is_available()
        if cuda_ok:
            print(f"✅ PyTorch {torch.__version__} — GPU: {torch.cuda.get_device_name(0)}.")
        else:
            print(f"ℹ️  PyTorch {torch.__version__} is CPU-only. Upgrading to CUDA version...")
    except ImportError:
        print("📦 Installing PyTorch with CUDA support...")

    if not cuda_ok:
        # Uninstall CPU version before installing CUDA version (different local version tag)
        subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "torch", "torchaudio", "-y"],
            capture_output=True
        )
        installed = False
        for cu_ver in ["cu128", "cu124"]:
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", "-q",
                    "torch", "torchaudio",
                    "--index-url", f"https://download.pytorch.org/whl/{cu_ver}"
                ])
                import importlib
                torch_mod = importlib.import_module("torch")
                if torch_mod.cuda.is_available():
                    print(f"✅ PyTorch ({cu_ver}) — GPU: {torch_mod.cuda.get_device_name(0)}.")
                    installed = True
                    break
            except Exception:
                continue
        if not installed:
            print("❌ Could not install PyTorch with CUDA. Check your NVIDIA drivers and re-run.")
            sys.exit(1)

    # --- llama-cpp-python (CUDA build required) ---
    llama_cuda_ok = False
    try:
        import llama_cpp
        llama_cuda_ok = llama_cpp.llama_supports_gpu_offload()
        if llama_cuda_ok:
            print("✅ llama-cpp-python already installed with CUDA support.")
        else:
            print("⚠️  llama-cpp-python is installed but has NO CUDA support (CPU-only build). Rebuilding...")
    except ImportError:
        print("📦 Installing llama-cpp-python (CUDA build from source — this takes a few minutes)...")

    if not llama_cuda_ok:
        subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "llama-cpp-python", "-y"],
            capture_output=True
        )
        nvcc = _find_nvcc()
        env = os.environ.copy()

        # Passing -DCMAKE_CUDA_COMPILER explicitly bypasses CMake's VS toolset detection,
        # which fails when the CUDA toolkit doesn't yet support the installed VS version.
        cmake_attempts = []
        if nvcc:
            cmake_attempts.append(f"-DGGML_CUDA=on -DCMAKE_CUDA_COMPILER={nvcc}")
        cmake_attempts.append("-DGGML_CUDA=on")  # default (may fail on VS 2026 + CUDA 13)

        installed = False
        for cmake_args in cmake_attempts:
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", "llama-cpp-python", "--no-cache-dir"],
                    env={**env, "CMAKE_ARGS": cmake_args}
                )
                # Verify the new build actually has CUDA
                import importlib
                lc = importlib.import_module("llama_cpp")
                if lc.llama_supports_gpu_offload():
                    print("✅ llama-cpp-python (CUDA) installed.")
                    installed = True
                    break
                else:
                    print(f"   Build completed but CUDA not detected. Trying next attempt...")
            except Exception:
                continue

        if not installed:
            print("❌ llama-cpp-python CUDA build failed.")
            print("   Ensure Visual Studio Build Tools with 'Desktop development with C++' is installed.")
            print("   Then re-run: python run.py")
            sys.exit(1)


def check_models():
    """Interactive Model Manager Menu."""
    # Delayed import to ensure dependencies are installed first
    try:
        import download_models
        from app.config import settings
    except ImportError:
        print("⚠️  Could not import model downloader. Skipping model checks.")
        return

    models_dir = settings.MODELS_DIR
    if not os.path.exists(models_dir):
        os.makedirs(models_dir)

    def get_status(path):
        return "✅ Installed" if os.path.exists(path) else "❌ Missing"

    while True:
        # Refresh model lists
        try:
            llm_models = download_models.LLM_MODELS
            whisper_models = download_models.WHISPER_MODELS
        except AttributeError:
             print("⚠️  Error fetching model lists.")
             return

        # Clear screen (optional based on preference, keeping simple print for now)
        print("\n" + "="*50)
        print("          🧠 AI MODEL MANAGER")
        print("="*50)
        
        print("\n--- LLM Models (Translation) ---")
        for i, model in enumerate(llm_models, 1):
            path = os.path.join(models_dir, model["file"])
            status = get_status(path)
            print(f"  {i}. {model['label']:<45} {status}")
            
        print("\n--- Whisper Models (Transcription) ---")
        offset = len(llm_models) + 1
        for i, model_name in enumerate(whisper_models, offset):
            is_installed = False
            cache_name = model_name.replace("/", "--")
            for item in os.listdir(models_dir):
                 if cache_name in item and os.path.isdir(os.path.join(models_dir, item)):
                     is_installed = True
                     break

            status = "✅ Installed" if is_installed else "❌ Missing"
            print(f"  {i}. Whisper {model_name:<36} {status}")

        qwen_idx = offset + len(whisper_models)
        is_installed = download_models.qwen_asr_installed()
        status = "✅ Installed" if is_installed else "❌ Missing"
        print(f"  {qwen_idx}. {download_models.QWEN_ASR['label']:<48} {status}")

        print("\n" + "-"*50)
        print(" [A] Download All    [U] Update All (force)    [R] Remove All    [C] Continue    [Q] Quit")
        print(" (Select a number to Manage/Update specific models)")

        choice = input("\n👉 Select an option: ").strip().upper()

        if choice == 'Q':
            print("Exiting...")
            sys.exit(0)
        elif choice == 'C':
            # Warn if no models found (basic check)
            any_llm = any(os.path.exists(os.path.join(models_dir, m["file"])) for m in llm_models)
            if not any_llm:
                print("\n⚠️  WARNING: No LLM models found. Translation features will not work.")
                confirm = input("   Are you sure you want to continue? (y/N): ").strip().lower()
                if confirm not in ['y', 'yes']:
                    continue
            print("\n✅ Setup complete. Launching app...")
            return
        elif choice == 'A':
            print("\n📥 Downloading all recommended models...")
            download_models.download_llms()
            download_models.download_whisper()
            download_models.download_qwen_asr_model()
            input("\nPress Enter to continue...")
        elif choice == 'U':
            confirm = input("\n🔄 Force re-download all models to get latest versions? (y/N): ").strip().lower()
            if confirm in ['y', 'yes']:
                print("\n📥 Updating all models...")
                for model in llm_models:
                    download_models.download_llm_model(model, force=True)
                for model_name in whisper_models:
                    download_models.download_whisper_model(model_name, force=True)
                download_models.download_qwen_asr_model(force=True)
                print("✅ All models updated.")
            input("\nPress Enter to continue...")
        elif choice == 'R':
            confirm = input("\n🗑️  Are you sure you want to remove ALL models? (y/N): ").strip().lower()
            if confirm in ['y', 'yes']:
                print("\n🗑️  Removing all models...")
                for model in llm_models:
                    download_models.remove_llm_model(model)
                for model_name in whisper_models:
                    download_models.remove_whisper_model(model_name)
                download_models.remove_qwen_asr_model()
                print("✅ All models removed.")
                input("\nPress Enter to continue...")
        elif choice.isdigit():
            idx = int(choice)
            
            # Handle LLM Selection
            if 1 <= idx <= len(llm_models):
                model = llm_models[idx-1]
                path = os.path.join(models_dir, model["file"])
                exists = os.path.exists(path)
                
                print(f"\nSelected: {model['label']}")
                if exists:
                    action = input("   [R] Remove  [U] Update/Verify  [B] Back : ").strip().upper()
                    if action == 'R':
                        download_models.remove_llm_model(model)
                    elif action == 'U':
                        download_models.download_llm_model(model, force=True)
                else:
                    action = input("   [I] Install  [B] Back : ").strip().upper()
                    if action == 'I':
                        download_models.download_llm_model(model)
                        
            # Handle Whisper Selection
            elif len(llm_models) < idx <= len(llm_models) + len(whisper_models):
                w_idx = idx - len(llm_models) - 1
                model_name = whisper_models[w_idx]
                
                # Check existence again for menu logic
                is_installed = False
                cache_name = model_name.replace("/", "--")
                for item in os.listdir(models_dir):
                     if cache_name in item and os.path.isdir(os.path.join(models_dir, item)):
                         is_installed = True
                         break
                
                print(f"\nSelected: Whisper {model_name}")
                if is_installed:
                    action = input("   [R] Remove  [U] Update/Verify  [B] Back : ").strip().upper()
                    if action == 'R':
                        download_models.remove_whisper_model(model_name)
                    elif action == 'U':
                        download_models.download_whisper_model(model_name, force=True)
                else:
                    action = input("   [I] Install  [B] Back : ").strip().upper()
                    if action == 'I':
                        download_models.download_whisper_model(model_name)

            # Handle Qwen3-ASR Selection
            elif idx == len(llm_models) + len(whisper_models) + 1:
                is_installed = download_models.qwen_asr_installed()
                print(f"\nSelected: {download_models.QWEN_ASR['label']}")
                print("   (requires the optional `qwen-asr` package: pip install qwen-asr)")
                if is_installed:
                    action = input("   [R] Remove  [U] Update/Verify  [B] Back : ").strip().upper()
                    if action == 'R':
                        download_models.remove_qwen_asr_model()
                    elif action == 'U':
                        download_models.download_qwen_asr_model(force=True)
                else:
                    action = input("   [I] Install  [B] Back : ").strip().upper()
                    if action == 'I':
                        download_models.download_qwen_asr_model()

            else:
                print("❌ Invalid selection.")
                import time
                time.sleep(1)

# Run startup checks before any other app imports
if __name__ == "__main__":
    check_dependencies()
    install_ai_packages()
    fix_cuda_paths()
    check_models()
    
    # Now that dependencies are checked/installed, import the app
    import uvicorn
    from app.main import app

    print("\n🚀 Starting AI Video Translator...")
    print("🔗 API docs: http://localhost:8000/docs")
    print("🔗 UI: http://localhost:8000/\n")
    
    # Run the FastAPI app which handles both API and static UI
    uvicorn.run(app, host="127.0.0.1", port=8000)

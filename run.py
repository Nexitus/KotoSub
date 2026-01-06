import sys
import subprocess
import os
import shutil

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

def fix_cuda_paths():
    """Finds and adds NVIDIA DLLs to the PATH on Windows."""
    if sys.platform != "win32":
        return

    import site
    packages_dirs = site.getsitepackages()
    if hasattr(site, "getusersitepackages"):
        packages_dirs.append(site.getusersitepackages())
    
    nvidia_dirs = [
        "nvidia/cudnn/bin",
        "nvidia/cublas/bin",
        "nvidia/cuda_runtime/bin",
        "nvidia/cuda_nvrtc/bin"
    ]
    
    for base in packages_dirs:
        for ndir in nvidia_dirs:
            full_path = os.path.join(base, ndir)
            if os.path.exists(full_path):
                os.environ["PATH"] = full_path + os.pathsep + os.environ["PATH"]
                if hasattr(os, "add_dll_directory"):
                    try:
                        os.add_dll_directory(full_path)
                    except Exception: pass

def check_gpu():
    print("🎮 Checking GPU status...")
    try:
        import torch
        if torch.cuda.is_available():
            device_name = torch.cuda.get_device_name(0)
            print(f"✅ CUDA is available! Found GPU: {device_name}")
        else:
            print("ℹ️  CUDA not detected by PyTorch. Local GPU processing will be disabled (using CPU).")
            print("   To enable GPU, ensure you have NVIDIA drivers and a compatible PyTorch installed.")
    except ImportError:
        print("⚠️  PyTorch not installed. Local GPU features will not work.")

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
            llm_models = download_models.get_llm_models()
            whisper_models = download_models.get_whisper_models()
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
            # Heuristic check for Whisper models (folder existence)
            # We assume if any faster-whisper folder exists with the name, it's likely installed.
            # A more robust check would use the same logic as remove_whisper_model or just check if directory exists in cache.
            # For simplicity in this UI, checking if *any* folder matches pattern in models_dir.
            is_installed = False
            for item in os.listdir(models_dir):
                 if "faster-whisper" in item and model_name in item and os.path.isdir(os.path.join(models_dir, item)):
                     is_installed = True
                     break
            
            status = "✅ Installed" if is_installed else "❌ Missing"
            print(f"  {i}. Whisper {model_name:<36} {status}")

        print("\n" + "-"*50)
        print(" [A] Download All Recommended    [R] Remove All    [C] Continue    [Q] Quit")
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
            input("\nPress Enter to continue...")
        elif choice == 'R':
            confirm = input("\n🗑️  Are you sure you want to remove ALL models? (y/N): ").strip().lower()
            if confirm in ['y', 'yes']:
                print("\n🗑️  Removing all models...")
                for model in llm_models:
                    download_models.remove_llm_model(model)
                for model_name in whisper_models:
                    download_models.remove_whisper_model(model_name)
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
                for item in os.listdir(models_dir):
                     if "faster-whisper" in item and model_name in item and os.path.isdir(os.path.join(models_dir, item)):
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
                        
            else:
                print("❌ Invalid selection.")
                import time
                time.sleep(1)

# Run startup checks before any other app imports
if __name__ == "__main__":
    check_dependencies()
    fix_cuda_paths()
    check_gpu()
    check_models()
    
    # Now that dependencies are checked/installed, import the app
    import uvicorn
    from app.main import app

    print("\n🚀 Starting AI Video Translator...")
    print("🔗 API docs: http://localhost:8000/docs")
    print("🔗 UI: http://localhost:8000/\n")
    
    # Run the FastAPI app which handles both API and static UI
    uvicorn.run(app, host="127.0.0.1", port=8000)

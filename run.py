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

# Run startup checks before any other app imports
if __name__ == "__main__":
    check_dependencies()
    fix_cuda_paths()
    check_gpu()
    
    # Now that dependencies are checked/installed, import the app
    import uvicorn
    from app.main import app

    print("\n🚀 Starting AI Video Translator...")
    print("🔗 API docs: http://localhost:8000/docs")
    print("🔗 UI: http://localhost:8000/\n")
    
    # Run the FastAPI app which handles both API and static UI
    uvicorn.run(app, host="127.0.0.1", port=8000)

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

# Run startup checks before any other app imports
if __name__ == "__main__":
    check_dependencies()
    
    # Now that dependencies are checked/installed, import the app
    import uvicorn
    from app.main import app

    print("\n🚀 Starting AI Video Translator...")
    print("🔗 API docs: http://localhost:8000/docs")
    print("🔗 UI: http://localhost:8000/\n")
    
    # Run the FastAPI app which handles both API and static UI
    uvicorn.run(app, host="127.0.0.1", port=8000)

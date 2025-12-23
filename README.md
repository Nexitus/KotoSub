# KotoSub - AI Video Subtitle Translator

KotoSub is a professional-grade video translation tool that automates the generation of localized subtitles. It features a modern React interface, a high-performance FastAPI backend, and support for both **Cloud-based** (OpenAI) and **Full Local** (CUDA GPU-accelerated) processing.

## ✨ Key Features

-   **Dual-Processing Modes**: Toggle between high-speed Cloud APIs and private, zero-cost Local GPU processing.
-   **Local GPU Acceleration**: Powered by `faster-whisper` and `llama-cpp-python` with full CUDA support.
-   **Parallel Processing Pipeline**: Concurrent translation and quality checking for significantly faster processing.
-   **Intelligent Localization**: Context-aware translation that focuses on intended meaning rather than literal word-for-word conversion.
-   **Readability Refinement**: Automatically splits long or fast subtitle segments for optimal viewing comfort.
-   **Automatic Language Detection**: Detects source languages automatically using the first 30 seconds of audio.
-   **Speaker Diarization**: Identifies and labels multiple speakers using `pyannote-audio`.
-   **Robust Error Recovery**: Built-in exponential backoff for API calls to handle rate limits and transient failures.
-   **GPU Audio Filters**: Integrated denoising (`afftdn`) and normalization (`loudnorm`) via FFmpeg.
-   **Built-in Burning**: Burn subtitles directly into the video using **NVENC (HEVC)** hardware acceleration.
-   **SRT & ASS Support**: Outputs industry-standard subtitle files.

## 📋 Pre-requisites

To run KotoSub, you need the following installed on your system:

1.  **Python 3.10+**
2.  **FFmpeg**: Must be in your system PATH.
3.  **NVIDIA GPU + CUDA**: Required for "Local" mode. Recommended: 8GB+ VRAM.
4.  **NVIDIA Container Toolkit**: Required if you wish to run in Docker with GPU acceleration.
5.  **Hugging Face Token**: Required for Speaker Diarization and downloading local models.
6.  **OpenAI API Key**: Required for "Cloud" mode.

## 🚀 Quick Start

### 1. Manual Installation
```bash
git clone https://github.com/Nexitus/KotoSub.git
cd KotoSub
pip install -r requirements.txt
python run.py
```

### 2. Docker Deployment (Recommended)
KotoSub is fully containerized for easy deployment. Ensure your Docker environment supports NVIDIA GPUs.
```bash
# Build and start the container
docker-compose up --build
```
This starts the application at `http://localhost:8000` with all dependencies (FFmpeg, CUDA, Python) pre-configured.

## 🌍 Language Support

KotoSub supports transcription from **over 30 source languages** (expandable) and translation into localized English:
- **East Asian**: Mandarin, Japanese, Korean, Taiwanese.
- **European**: Spanish, French, German, Portuguese, Italian, Dutch, etc.
- **Eastern European**: Russian, Polish, Ukrainian, Czech, Romanian, etc.

## 🛠️ Configuration
Settings are managed directly through the web UI and persisted in your browser's local storage. This includes:
- API Keys / Base URLs.
- Model selection (Whisper-large-v3, Mistral, Llama 3, etc.).
- Output directory preferences.

---

## Architecture
KotoSub uses a modular Python backend for heavy AI lifting and a Vite+React frontend for a sleek, responsive user experience. Communication is handled via NDJSON streams for real-time progress updates.

# KotoSub - AI Video Subtitle Translator

KotoSub is a professional-grade video translation tool that automates the generation of localized subtitles. It features a modern React interface, a high-performance FastAPI backend, and support for both **Cloud-based** (OpenAI) and **Full Local** (CUDA GPU-accelerated) processing.

## ✨ Key Features

### Core Translation Capabilities
-   **Dual-Processing Modes**: Toggle between high-speed Cloud APIs and private, zero-cost Local GPU processing.
-   **Local GPU Acceleration**: Powered by `faster-whisper` and `llama-cpp-python` with full CUDA support.
-   **Parallel Processing Pipeline**: Concurrent translation and quality checking for up to **5x faster processing** on long videos.
-   **Intelligent Localization**: Context-aware translation that focuses on intended meaning rather than literal word-for-word conversion.
-   **AI Quality Verification**: Automated second-pass quality check to ensure translation accuracy and context preservation.
-   **Automatic Language Detection**: Detects source languages automatically using the first 30 seconds of audio.

### Advanced Features
-   **Speaker Diarization**: Identifies and labels multiple speakers using `pyannote-audio`.
-   **Readability Refinement**: Automatically splits long or fast subtitle segments based on CPS (Characters Per Second) for optimal viewing comfort.
-   **Audio Pre-processing**: Integrated denoising (`afftdn`) and normalization (`loudnorm`) via FFmpeg for improved transcription accuracy.
-   **Multiple Subtitle Formats**: Export as **SRT** (Standard), **ASS** (Advanced Stylized Subtitles), or **VTT** (WebVTT for web players).
-   **Built-in Subtitle Burning**: Burn subtitles directly into video using **NVENC (HEVC)** hardware acceleration with CPU fallback.
-   **Output Customization**: Configurable file naming templates with custom suffixes and language code inclusion.
-   **Live Log Streaming**: Real-time stdout capture with progressive scrolling for full transparency into FFmpeg and AI processing.

### Reliability & Performance
-   **Robust Error Recovery**: Built-in exponential backoff for API calls to handle rate limits and transient failures.
-   **Dockerized Deployment**: Multi-stage Docker build with NVIDIA GPU support for consistent, reproducible environments.
-   **Batch Processing**: Sequential processing of multiple videos with comprehensive progress tracking.

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
Use Docker Compose v2.24+ with NVIDIA GPU support (Docker Desktop's WSL2 backend on Windows, or NVIDIA Container Toolkit on Linux). The default build targets an RTX 5070 Ti / Blackwell GPU (compute capability 12.0).

```bash
# Build and start the container
docker compose up -d --build --wait

# Follow logs or stop the app
docker compose logs -f kotosub
docker compose down
```

Open `http://localhost:8000`. The container serves both the UI and API; `/health` reports web-server readiness. It binds to localhost on the host.

The image installs FFmpeg, CUDA 12.8, cuDNN 9, PyTorch, and CUDA-enabled llama-cpp-python during the build. Startup launches FastAPI directly without the interactive `run.py` installer. The first build downloads several GB and compiles llama.cpp.

- Existing `./models` and `./output` folders are mounted into the container and survive rebuilds and `docker compose down`.
- An optional `.env` supplies application settings and `HF_TOKEN` at runtime; it is excluded from the image. Container data paths are fixed under `/app`.
- UI settings remain in browser local storage. Set the UI output directory to `/app/output` (or leave it empty to use the default); Windows host paths are unavailable inside the container. Upload videos through the UI.
- Models are reused from `./models` or downloaded when selected for processing. Gated models require a Hugging Face token and accepted model terms.
- Optional pyannote diarization and COMET quality scoring are not installed in the base image; quality checking uses the app's existing heuristics.

For another NVIDIA GPU, set its compute capability at build time (for example, `89` for RTX 40-series):
```bash
docker compose build --build-arg CUDA_ARCHITECTURES=89
docker compose up -d --wait
```

Check GPU access separately from web-server health:
```bash
docker compose exec kotosub python -c "import torch, llama_cpp; assert torch.cuda.is_available(); assert llama_cpp.llama_supports_gpu_offload(); print(torch.cuda.get_device_name(0))"
```

## 🌍 Language Support

KotoSub supports transcription from **over 30 source languages** with automatic detection:
- **East Asian**: Mandarin, Japanese, Korean, Taiwanese
- **European**: Spanish, French, German, Portuguese, Italian, Dutch
- **Eastern European**: Russian, Polish, Ukrainian, Czech, Romanian, Bulgarian, Croatian, Serbian, Slovenian
- **Nordic**: Swedish, Danish, Norwegian, Finnish
- **Other**: Greek, Turkish, Hungarian, Slovak

Translation currently targets **localized English** with plans for expanded target language support.

## 🤖 Supported Models

### Whisper Models (Transcription)
- **Cloud**: OpenAI Whisper API (`whisper-1`)
- **Local**: `large-v3`, `large-v3-turbo`, `medium` (via `faster-whisper`)

### LLM Models (Translation)
- **Cloud**: Any OpenAI-compatible API (GPT-4, GPT-3.5-turbo, etc.)
- **Local** (GGUF format via `llama-cpp-python`):
  - **Qwen 3 8B** - Strong multilingual performance, Chinese-native
  - **Dolphin 2.8 Mistral** - Uncensored, creative translations
  - **Noromaid 7B v0.4** - Creative/NSFW content handling
  - **OpenHermes 2.5** - High quality, low filtering
  - **Gemma 2 9B** - Google's fast, efficient model

## 🛠️ Configuration
Settings are managed directly through the web UI and persisted in your browser's local storage:
- **API Configuration**: OpenAI API keys, base URLs, and model selection
- **Local Models**: Whisper model size, LLM model selection, automatic model downloading
- **Output Settings**: Custom output directory, file naming templates, subtitle format selection
- **Processing Options**: Speaker diarization, subtitle burning, audio preprocessing
- **Hugging Face Token**: For model downloads and diarization

## 📊 Live Monitoring
The built-in **Live Logs** feature provides real-time visibility into:
- FFmpeg audio extraction and encoding operations
- Whisper transcription progress
- LLM translation and quality verification passes
- Subtitle generation and formatting
- Error messages and debugging information

---

## 🏗️ Architecture
KotoSub uses a modular Python backend for heavy AI lifting and a Vite+React frontend for a sleek, responsive user experience. Communication is handled via **NDJSON streams** for real-time progress updates and live log streaming.

## 📝 License
This project is open source and available for personal and commercial use.

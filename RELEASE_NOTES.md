# KotoSub v1.0.0

We are excited to announce the first official semantic release of **KotoSub (v1.0.0)**! This version marks a major milestone in providing a powerful, local-first, and privacy-respecting solution for AI-powered video translation and subtitle generation.

## 🚀 Key Features

### 🎙️ Advanced Transcription & Translation
- **Local GPU Acceleration**: Full support for CUDA-accelerated transcription (faster-whisper) and translation (llama-cpp-python).
- **Multiple LLM Support**: Seamlessly switch between local models (like the newly added **Qwen-3-8B**) and API providers.
- **Smart Model Management**: A dedicated CLI (`run.py`) to easily install, update, and manage your local AI models.

### 🎬 Professional Video Processing
- **Subtitle Burn-in**: High-quality HEVC (H.265) NVENC hardware-accelerated video encoding for permanent subtitles.
- **Automated Workflows**: One-click process from raw video to translated, captioned output.
- **Customizable Output**: Full control over file naming conventions and output directories.

### 📊 Modern UI/UX
- **Real-time Streaming Logs**: Live, auto-scrolling feedback during the translation process.
- **Premium Design**: A sleek, premium, and responsive user interface with "Glassmorphism" aesthetics.
- **Persistent Settings**: Your API keys, model choices, and preferences are automatically saved between sessions.

---

## 🛠️ Technical Enhancements
- **Refined Model List**: Optimized for performance and quality by focusing on Large-V3-Turbo (Whisper) and Qwen-3 (LLM) architectures.
- **Robust Error Handling**: Improved retry logic and logging for API interactions.
- **Clean Architecture**: Decoupled frontend (React/Vite) and backend (FastAPI/Python) for scalability.

---

*Thank you for being part of the KotoSub journey!*

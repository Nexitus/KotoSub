# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**KotoSub** is an AI-powered video subtitle translation tool. It uses a FastAPI Python backend for heavy AI processing and a Vite+React (TypeScript) frontend. Communication uses NDJSON streams for real-time progress updates.

## Commands

### Backend

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application (includes interactive model manager and dependency checks)
python run.py

# Run FastAPI directly (skips startup checks)
uvicorn app.main:app --host 127.0.0.1 --port 8000

# Download models standalone
python download_models.py
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Dev server (proxies to backend at localhost:8000)
npm run dev

# Build for production (output goes to frontend/dist/, served by FastAPI)
npm run build
```

### Docker

```bash
# Build and start with GPU support
docker-compose up --build
```

### Tests

```bash
# Run all tests
python -m pytest tests/

# Run a single test file
python -m pytest tests/test_video.py

# Run with unittest
python -m unittest tests/test_video.py
```

## Architecture

### Request Flow

1. User uploads video via React frontend
2. Frontend POSTs to `/api/translate_stream` (multipart form: video file + JSON config)
3. FastAPI saves video to temp file, starts a background thread
4. Thread runs `VideoTranslatorApp.process()` in `app/core.py`
5. Progress events are queued and streamed back as NDJSON via `StreamingResponse`
6. Frontend reads the NDJSON stream and updates UI

### Backend Structure (`app/`)

- **`main.py`** — FastAPI app with all API routes. Serves the React build from `frontend/dist/` as static files.
- **`core.py`** — `VideoTranslatorApp.process()` orchestrates the full pipeline. Also intercepts `sys.stdout` to forward print logs to the frontend "Live Logs" stream (step=`"log"`).
- **`config.py`** — Pydantic `Settings` loaded from `.env`. Key vars: `HF_TOKEN`, `MODELS_DIR`, `OUTPUT_DIR`, `TEMP_DIR`.
- **`processors/`** — Independent service classes:
  - `video.py` — FFmpeg wrapper: validate, extract audio (with denoising/normalization), burn subtitles (NVENC/CPU), get duration
  - `transcription.py` — Local `faster-whisper` transcription (CUDA/CPU) with VAD filter
  - `translation.py` — Local `llama-cpp-python` translation (sequential, locked). Includes `quality_check()` second pass and `_clean_translation()` to strip hallucinations/watermarks.
  - `subtitles.py` — Generates SRT, VTT, ASS formats; `refine_segments()` splits high-CPS segments
  - `diarization.py` — `pyannote-audio` speaker identification, assigned to segments before translation

### Local GPU & CUDA Support

KotoSub runs entirely offline via local engines:
- **Transcription**: `faster-whisper` using CUDA GPU (float16 compute type) or CPU fallback (int8 compute type).
- **Translation**: `llama-cpp-python` loading GGUF models directly on the GPU using `-DGGML_CUDA=on`.

On Windows, both local services call `_fix_cuda_paths()` to add NVIDIA DLL directories from pip package paths to `PATH` and `os.add_dll_directory()`.

### Model Management

`download_models.py` defines `LLM_MODELS` (GGUF files from HuggingFace) and `WHISPER_MODELS`. `run.py` launches an interactive CLI model manager before starting the server. The `/api/models` endpoint exposes installed/missing model status to the frontend.

Models are stored in `settings.MODELS_DIR` (default: `./models/`). Whisper models are detected by scanning for `faster-whisper` directory names.

### Frontend

Built with Vite + React 19 + TypeScript, using CDN-loaded Tailwind CSS. The production build is placed in `frontend/dist/` and served by FastAPI's `StaticFiles` mount. The frontend consumes the NDJSON stream to show step-by-step progress (validation → extraction → transcription → diarization → translation → quality_check → refinement → generation → burn_in).

### In-Memory Job Store

`app/main.py` maintains a global `jobs` dict keyed by `job_id` (UUID). This is ephemeral.

## Key Environment Variables (`.env`)

| Variable | Purpose |
|---|---|
| `HF_TOKEN` | HuggingFace token for diarization and model downloads |
| `MODELS_DIR` | Override default `./models/` path |
| `OUTPUT_DIR` | Override default `./output/` path |

## Design Context

### Users
Content creators and YouTubers — non-technical users who want fast, quality subtitles with minimal friction. They use the app mid-workflow (after filming, before publishing). Time pressure is real; confusion is costly.

### Brand Personality
**Fast. Smart. Effortless.** The UI does the heavy lifting invisibly. Think Vercel's deploy dashboard or Arc Browser — confident, clean, ahead of the user.

### Aesthetic Direction
- Light mode default + full dark mode (system `prefers-color-scheme`)
- Modern minimal with purposeful accents — not sterile, not loud
- Brand anchors: purple `#4B286D` (primary/active) and green `#2B8000` (CTA/success)
- Semantic token layer required for light/dark switching
- Inter typeface — tighter hierarchy, stronger weight contrast
- Motion: subtle and purposeful only (progress bars, status transitions)

### Design Principles
1. **Speed signals matter** — Instant feedback, smooth progress, no dead-end loading states
2. **Effortless defaults, accessible depth** — Smart defaults; advanced options stay out of the way
3. **One clear action at a time** — One primary action per screen state, no competing CTAs
4. **Status is never ambiguous** — Always: idle / uploading / processing / done / failed
5. **Consistency earns trust** — Systematic spacing, color, and interaction patterns

## Windows GPU Notes

- Local GPU requires `nvidia-cudnn-cu12` and `nvidia-cublas-cu12` pip packages
- `run.py` and each processor call `_fix_cuda_paths()` to resolve DLL loading issues specific to Windows
- `llama-cpp-python` must be built with CUDA support (`CMAKE_ARGS="-DGGML_CUDA=on"`) or a prebuilt wheel used


# KotoSub v1.1.0

## 🚀 Highlights

### Transcription Pipeline
- **New VAD module** (`app/processors/vad.py`) for robust voice activity detection
- **Qwen ASR support** (`app/processors/qwen_asr.py`) with dedicated whisper worker process (`app/processors/whisper_worker.py`)
- **Live processing** (`app/processors/live.py`) and consolidated CUDA path handling (`app/cuda.py`)
- Documented pipeline architecture in `docs/TRANSCRIPTION_PIPELINE.md`

### Frontend Redesign
- **New components**: DropZone, LogsConsole, OptionsDrawer, ResultsPanel, StageCanvas, StepRail
- **Reusable UI primitives**: Banner, CheckboxField, FormLabel, Input, Select, TabGroup
- Local CSS (`index.css`), public assets, and a cleaner index.html shell
- Removed legacy Gemini service and metadata.json

### Backend
- Refined config, core orchestration, and all processors (transcription, translation, subtitles, diarization, video)
- Removed deprecated Gradio UI and obsolete docs/scripts
- Added test suite scaffolding (legal `.py` tests are versioned; artifacts ignored)

### Infrastructure
- Updated Dockerfile, docker-compose, ignores, and packaging
- Project guidance (CLAUDE.md) and wireframe/PRD docs for the iOS live app

**Full build included as asset:** `frontend-dist-v1.1.0.zip` — the compiled Vite/React production build served by FastAPI.

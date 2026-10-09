# Stage 1: Build Frontend
FROM node:22-bookworm-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Runtime Environment
FROM nvidia/cuda:12.8.1-cudnn-devel-ubuntu22.04

# ponytail: target the RTX 5070 Ti; override at build time for other GPU architectures.
ARG CUDA_ARCHITECTURES=120

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    MODELS_DIR=/app/models \
    OUTPUT_DIR=/app/output \
    TEMP_DIR=/app/temp \
    TMPDIR=/app/temp \
    HF_HOME=/app/models/huggingface \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility,video

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 \
    python3-pip \
    python3-dev \
    build-essential \
    pkg-config \
    ffmpeg \
    libsndfile1 \
    fonts-dejavu-core \
    fonts-noto-cjk \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s /usr/bin/python3.10 /usr/bin/python

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip cmake ninja \
    && python -m pip install --no-cache-dir torch==2.10.0 torchaudio==2.10.0 \
        --index-url https://download.pytorch.org/whl/cu128 \
    && python -m pip install --no-cache-dir -r requirements.txt
RUN mkdir -p /app/models /app/output /app/temp
RUN CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=${CUDA_ARCHITECTURES}" \
    CMAKE_BUILD_PARALLEL_LEVEL=2 \
    python -m pip install --no-cache-dir --no-binary=llama-cpp-python llama-cpp-python==0.3.36
# Optional Qwen3-ASR engine (word timestamps via ForcedAligner). Placed after
# the llama-cpp layer so this stays a cheap incremental rebuild. Keep in sync
# with the guard in app/main.py and the note in requirements.txt.
RUN python -m pip install --no-cache-dir qwen-asr
RUN python -c "from pathlib import Path; import importlib.util, torch, torchaudio, faster_whisper; assert torch.version.cuda == '12.8'; assert list(Path(importlib.util.find_spec('llama_cpp').origin).parent.rglob('libggml-cuda.so'))" \
    && python -m pip check

COPY app/ ./app
COPY download_models.py .
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import json, urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3))['status'] == 'ok'"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

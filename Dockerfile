# Stage 1: Build Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Runtime Environment
FROM nvidia/cuda:12.1.1-devel-ubuntu22.04

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    MODELS_DIR=/app/models \
    OUTPUT_DIR=/app/output

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    ffmpeg \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

# Fix python symlink
RUN ln -s /usr/bin/python3.10 /usr/bin/python

# Install Python dependencies
COPY requirements.txt .
# Install with CUDA support for llama-cpp-python
RUN CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY app/ ./app
COPY run.py .
COPY download_models.py .

# Copy built frontend assets from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create necessary directories
RUN mkdir -p /app/models /app/output /app/temp

# Expose port
EXPOSE 8000

# Default command
CMD ["python", "run.py"]

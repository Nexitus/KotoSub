from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, FileResponse, HTMLResponse
from pydantic import BaseModel
import os
import json
import asyncio
import threading
import queue
import shutil
import tempfile
import uuid
from typing import Optional
from app.core import VideoTranslatorApp
from app.processors.live import LiveTranslationEngine
from app.processors.video import VideoProcessor
from app.config import settings

app = FastAPI(title="Video Subtitle Translator API")
translator = VideoTranslatorApp()

# In-memory live session store
live_sessions = {}

# Model download state (Settings → download missing models); a single worker
# thread runs at most one download batch — same behavior as the run.py manager.
model_download_state = {"active": False, "kind": None, "logs": [],
                        "error": None, "finished": False}

def _whisper_installed(model_name: str, models_dir: str) -> bool:
    cache_name = model_name.replace("/", "--")
    if not os.path.exists(models_dir):
        return False
    for item in os.listdir(models_dir):
        if cache_name in item and os.path.isdir(os.path.join(models_dir, item)):
            return True
    return False

def _run_model_downloads(kind: str):
    """Downloads MISSING models of the requested kind in a worker thread.
    All logging goes to model_download_state['logs'] (surfaced in Settings)."""
    import download_models
    state = model_download_state

    def log(msg: str):
        state["logs"] = (state["logs"] + [msg])[-199:]
        print(msg)

    def set_status(installed: bool):
        return "✅ Installed" if installed else "❌ Missing"

    try:
        models_dir = settings.MODELS_DIR
        os.makedirs(models_dir, exist_ok=True)

        if kind in ("llm", "all"):
            log("--- LLM Models (Translation) ---")
            for model in download_models.LLM_MODELS:
                path = os.path.join(models_dir, model["file"])
                log(f"{model['label']}: {set_status(os.path.exists(path))}")
                if not os.path.exists(path):
                    download_models.download_llm_model(model)
        if kind in ("whisper", "all"):
            log("--- Whisper Models (Transcription) ---")
            for model_name in download_models.WHISPER_MODELS:
                is_installed = _whisper_installed(model_name, models_dir)
                log(f"Whisper {model_name}: {set_status(is_installed)}")
                if not is_installed:
                    download_models.download_whisper_model(model_name)
        if kind in ("qwen", "all"):
            log("--- Qwen3-ASR (Alternative Transcription) ---")
            is_installed = download_models.qwen_asr_installed()
            log(f"{download_models.QWEN_ASR['label']}: {set_status(is_installed)}")
            if not is_installed:
                download_models.download_qwen_asr_model()

        if state["error"] is None:
            log("✅ Download finished")
    except Exception as e:
        state["error"] = str(e)
        log(f"❌ Download failed: {e}")
    finally:
        state["active"] = False
        state["finished"] = True

class ModelDownloadRequest(BaseModel):
    kind: str = "all"  # "llm" | "whisper" | "qwen" | "all"

@app.post("/api/models/download")
def start_model_downloads(req: ModelDownloadRequest):
    """Starts downloads for MISSING models of the requested kind in the
    background; poll /api/models/download/status for progress."""
    import download_models
    if req.kind not in ("llm", "whisper", "qwen", "all"):
        raise HTTPException(status_code=400, detail=f"Unknown kind: {req.kind}")
    if req.kind in ("qwen", "all"):
        import importlib.util
        if importlib.util.find_spec("qwen_asr") is None:
            raise HTTPException(status_code=400,
                                detail="Qwen3-ASR needs the optional qwen-asr package. "
                                       "Install it on the server with: pip install qwen-asr")
    if model_download_state["active"]:
        raise HTTPException(status_code=409, detail="A model download is already running")
    model_download_state.update({"active": True, "kind": req.kind, "logs": [],
                                 "error": None, "finished": False})
    threading.Thread(target=_run_model_downloads, args=(req.kind,), daemon=True).start()
    return {"started": True, "kind": req.kind}

@app.get("/api/models/download/status")
def model_downloads_status():
    state = model_download_state
    return {"active": state["active"], "kind": state["kind"],
            "logs": state["logs"][-100:], "error": state["error"],
            "finished": state["finished"]}



@app.post("/api/translate_stream")
async def translate_stream(
    video: UploadFile = File(...),
    config: str = Form(...)
):
    """
    Streaming endpoint that returns NDJSON progress events.
    """
    config_data = json.loads(config)
    
    # Save uploaded file to temp
    suffix = os.path.splitext(video.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(video.file, tmp)
        temp_video_path = tmp.name

    q = queue.Queue()

    def progress_callback(progress, message, step=None, segment=None):
        # Handle 'log' step for live log streaming
        if step == 'log':
            q.put({
                "step": "log",
                "progress": 0,
                "message": message,
                "status": "processing"
            })
            return

        prog_val = int(progress * 100) if progress is not None else 0

        event = {
            "step": step or "processing",
            "progress": prog_val,
            "message": message,
            "status": "processing"
        }
        if segment is not None:
            event["segment"] = segment
        q.put(event)

    def run_process():
        try:
            result = translator.process(
                video_path=temp_video_path,
                source_lang=config_data.get("sourceLang"),
                target_lang=config_data.get("targetLang", "en"),
                whisper_model=config_data.get("whisperModel"),
                llm_model=config_data.get("llmModel"),
                local_llm_file=config_data.get("localLlmFile"),
                whisper_prompt=config_data.get("whisperPrompt"),
                whisper_hotwords=config_data.get("whisperHotwords"),
                output_dir=config_data.get("outputDir"),
                hf_token=config_data.get("apiKeys", {}).get("huggingFace"),
                use_diarization=config_data.get("enableDiarization", False),
                use_quality_check=config_data.get("qualityVerification", True),
                burn_subtitles=config_data.get("burnSubtitles", False),
                use_gpu_encoding=config_data.get("useGpuEncoding", False),
                # New parameters:
                subtitle_format=config_data.get("subtitleFormat", "srt"),
                output_suffix=config_data.get("outputSuffix", "_translated"),
                include_language_in_name=config_data.get("includeLanguageInName", True),
                burn_options={
                    "font": config_data.get("font"),
                    "font_size": config_data.get("fontSize"),
                    "position": config_data.get("position"),
                    "shadow": config_data.get("shadow"),
                    "outline": config_data.get("outline")
                },
                progress_callback=progress_callback
            )
            completion_data = {
                "step": "completed",
                "progress": 100,
                "message": "Translation completed successfully",
                "status": "completed",
                "result": result
            }
            q.put(completion_data)
        except Exception as e:
            error_data = {
                "step": "error",
                "progress": 0,
                "message": str(e),
                "status": "error"
            }
            q.put(error_data)
        finally:
            q.put(None) # Sentinel
            if os.path.exists(temp_video_path):
                os.remove(temp_video_path)

    threading.Thread(target=run_process).start()

    async def event_generator():
        while True:
            # blocking get runs in a thread pool; wakes instantly on each event
            event = await asyncio.to_thread(q.get)
            if event is None:
                break
            yield json.dumps(event) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

class LiveStartRequest(BaseModel):
    video_path: str
    source_lang: str = "auto"
    target_lang: str = "en"
    lookahead_seconds: float = None
    whisper_model: Optional[str] = None
    llm_model: Optional[str] = None
    local_llm_file: Optional[str] = None

def _vram_mb() -> int:
    try:
        import torch
        if torch.cuda.is_available():
            return torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
    except ImportError:
        pass
    return 0

def _auto_select_llm():
    vram_mb = _vram_mb()
    if vram_mb >= 24000:
        return settings.LOCAL_LLM_MODEL, settings.LOCAL_LLM_FILE
    if vram_mb >= 12000:
        return settings.LIVE_FALLBACK_LLM_MODEL, settings.LIVE_FALLBACK_LLM_FILE
    return "unsloth/Qwen3.5-4B-GGUF", "Qwen3.5-4B-Q4_K_M.gguf"

@app.post("/api/live/start")
def live_start(req: LiveStartRequest):
    if not os.path.exists(req.video_path):
        raise HTTPException(status_code=400, detail=f"Video file not found: {req.video_path}")
    return _start_live_session(video_path=req.video_path, source_lang=req.source_lang,
        target_lang=req.target_lang, lookahead_seconds=req.lookahead_seconds,
        whisper_model=req.whisper_model, llm_model=req.llm_model, local_llm_file=req.local_llm_file,
        temp_upload_path=None)

def _teardown_session(session: dict):
    try:
        session["engine"].stop()
    except Exception:
        pass
    for path in (session.get("remuxed_path"), session.get("temp_upload_path")):
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass
    engine = session.get("engine")
    if engine and engine.hls_dir:
        shutil.rmtree(engine.hls_dir, ignore_errors=True)

def _cleanup_all_live_sessions():
    for old_id, old_session in list(live_sessions.items()):
        _teardown_session(old_session)
        live_sessions.pop(old_id, None)

def _llm_fits_vram(local_llm_file: str) -> bool:
    vram_mb = _vram_mb()
    if not vram_mb:
        return True
    file_path = os.path.join(settings.MODELS_DIR, local_llm_file or "")
    try:
        size_mb = os.path.getsize(file_path) // (1024 * 1024)
    except OSError:
        return True
    if size_mb == 0:
        return True
    return (size_mb + 6144) < vram_mb

def _start_live_session(video_path, source_lang, target_lang, lookahead_seconds, whisper_model, llm_model, local_llm_file, temp_upload_path=None) -> dict:
    _cleanup_all_live_sessions()
    can_play, needs_remux, reason = VideoProcessor().is_browser_playable(video_path)
    needs_transcode = not can_play and not needs_remux
    if needs_transcode:
        print(f"[Live] {reason} — scheduling automatic H.264 conversion")

    remuxed = False
    remux_path = None
    if needs_remux:
        remux_path = os.path.join(settings.LIVE_REMUX_DIR, f"{os.path.splitext(os.path.basename(video_path))[0]}_remux.mp4")
        video_path = VideoProcessor().remux_to_mp4(video_path, remux_path)
        remuxed = True

    duration = VideoProcessor().get_duration(video_path)

    if llm_model is None:
        llm_model, local_llm_file = _auto_select_llm()
    elif not _llm_fits_vram(local_llm_file):
        print(f"[Live] Requested LLM '{local_llm_file}' plus Whisper exceeds VRAM, falling back to auto-selected model")
        llm_model, local_llm_file = _auto_select_llm()

    lookahead = lookahead_seconds if lookahead_seconds is not None else settings.LIVE_LOOKAHEAD_SECONDS
    session_id = str(uuid.uuid4())

    engine = LiveTranslationEngine(
        video_path=video_path,
        source_lang=source_lang,
        target_lang=target_lang,
        lookahead_seconds=lookahead,
        whisper_model=whisper_model,
        llm_model=llm_model,
        local_llm_file=local_llm_file,
        transcode_to_h264=needs_transcode,
        session_id=session_id,
    )
    engine.remuxed = remuxed
    engine.start()
    live_sessions[session_id] = {"engine": engine, "remuxed_path": remux_path if remuxed else None, "temp_upload_path": temp_upload_path, "last_segment_count": 0}

    return {"session_id": session_id, "video_path": video_path, "duration": duration, "remuxed": remuxed, "transcoding": needs_transcode, "hls": needs_transcode}

@app.post("/api/live/start_upload")
def live_start_upload(video: UploadFile = File(...), config: str = Form(...)):
    suffix = os.path.splitext(video.filename)[1] or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(video.file, tmp)
        temp_path = tmp.name
    try:
        config_data = json.loads(config)
        return _start_live_session(
            video_path=temp_path,
            source_lang=config_data.get("source_lang", "auto"),
            target_lang=config_data.get("target_lang", "en"),
            lookahead_seconds=config_data.get("lookahead_seconds"),
            whisper_model=config_data.get("whisper_model"),
            llm_model=config_data.get("llm_model"),
            local_llm_file=config_data.get("local_llm_file"),
            temp_upload_path=temp_path,
        )
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise

@app.get("/api/live/video/{session_id}")
def live_video(session_id: str):
    session = live_sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    engine = session["engine"]
    video_path = engine.video_path
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    if engine.transcoding:
        # HLS session — the original (HEVC/AV1) can't be served, browser plays it
        # via /api/live/hls/... instead. Fail fast so a wrong mount is obvious.
        raise HTTPException(status_code=503, detail="Video needs conversion — served via HLS playlist")
    return FileResponse(video_path, media_type="video/mp4", content_disposition_type="inline")

@app.get("/api/live/hls/{session_id}/{filename}")
def live_hls(session_id: str, filename: str):
    """Serve the growing HLS event playlist, fMP4 init and segments.
    ffmpeg writes relative filenames, so hls.js resolves them against this route."""
    session = live_sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    engine = session["engine"]
    root = os.path.abspath(engine.hls_dir or "")
    full = os.path.abspath(os.path.join(root, filename))
    if os.path.commonpath([root, full]) != root or not os.path.isfile(full):
        raise HTTPException(status_code=404, detail="Playlist or segment not found")
    media_type = "application/vnd.apple.mpegurl" if filename.endswith(".m3u8") else "video/mp4"
    return FileResponse(full, media_type=media_type, content_disposition_type="inline")

@app.get("/api/live/status/{session_id}")
def live_status(session_id: str, position: float = None, state: str = None):
    session = live_sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    engine = session["engine"]
    if position is not None:
        engine.update_position(position, state or "Playing")
    status = engine.get_status()
    new_segment_count = len(status["segments"]) - session["last_segment_count"]
    session["last_segment_count"] = len(status["segments"])
    filename = os.path.basename(status["filepath"]) if status["filepath"] else None
    return {
        **status,
        "session_id": session_id,
        "filename": filename,
        "new_segment_count": new_segment_count,
    }

@app.post("/api/live/stop/{session_id}")
def live_stop(session_id: str):
    session = live_sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    srt_file_path = session["engine"].srt_file_path
    _teardown_session(session)
    del live_sessions[session_id]
    return {"srt_file_path": srt_file_path}

@app.get("/api/download")
def download_file(path: str = Query(...)):
    """
    Download endpoint for processed files.
    """
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=os.path.basename(path))

@app.get("/api/models")
def get_available_models():
    """
    Returns lists of available and missing models.
    """
    import download_models

    models_dir = settings.MODELS_DIR
    
    llm_status = []
    for model in download_models.LLM_MODELS:
        path = os.path.join(models_dir, model["file"])
        llm_status.append({
            **model,
            "installed": os.path.exists(path)
        })

    whisper_status = []
    for model_name in download_models.WHISPER_MODELS:
        is_installed = False
        if os.path.exists(models_dir):
            cache_name = model_name.replace("/", "--")
            for item in os.listdir(models_dir):
                if cache_name in item and os.path.isdir(os.path.join(models_dir, item)):
                    is_installed = True
                    break
        whisper_status.append({
            "label": f"Whisper {model_name}",
            "value": model_name,
            "installed": is_installed
        })

    # Alternative engine (same transcription selector; Whisper stays default)
    whisper_status.append({
        "label": download_models.QWEN_ASR["label"],
        "value": download_models.QWEN_ASR["value"],
        "installed": download_models.qwen_asr_installed()
    })

    return {
        "llm_models": llm_status,
        "whisper_models": whisper_status,
        "recommended": dict(download_models.RECOMMENDED_BY_LANG)
    }

@app.get("/api/gpu-info")
def get_gpu_info():
    """
    Returns GPU name, VRAM, and supported codecs for the frontend.
    """
    info = {"available": False, "name": None, "vram_total_mb": None, "detected_gpu": False}
    vram_mb = _vram_mb()
    if vram_mb:
        import torch
        info["available"] = True
        info["name"] = torch.cuda.get_device_name(0)
        info["vram_total_mb"] = vram_mb
        info["detected_gpu"] = True
    return info

@app.get("/health")
def health_check():
    return {"status": "ok"}

# Mount frontend static files
# We assume the build output is in frontend/dist
frontend_path = os.path.join(os.getcwd(), "frontend", "dist")

# Mount dist last so it doesn't shadow the API
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    @app.get("/")
    async def root_fallback():
        return {"message": "Frontend not found. Please build the frontend in /frontend directory."}

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
from typing import Optional
from app.core import VideoTranslatorApp

app = FastAPI(title="Video Subtitle Translator API")
translator = VideoTranslatorApp()

# In-memory job store for progress persistence
# In a production app, this would be Redis or a database
jobs = {}



@app.post("/api/translate_stream")
async def translate_stream(
    video: UploadFile = File(...),
    config: str = Form(...)
):
    """
    Streaming endpoint that returns NDJSON progress events.
    """
    import uuid
    job_id = str(uuid.uuid4())
    config_data = json.loads(config)
    
    # Save uploaded file to temp
    suffix = os.path.splitext(video.filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        shutil.copyfileobj(video.file, tmp)
        temp_video_path = tmp.name

    q = queue.Queue()

    def progress_callback(progress, message, step=None):
        # Map internal status to frontend steps if needed, 
        # or just pass through logic based on message content
        # For simplicity, we'll try to extract "step" from message or use provided step
        
        # Heuristic mapping for progress_callback calls in core.py
        current_step = step or "processing"
        if "Validating" in message: current_step = "validation"
        elif "Extracting" in message: current_step = "extraction"
        elif "Transcribing" in message: current_step = "transcription"
        elif "Identifying" in message: current_step = "diarization"
        elif "Translating" in message: current_step = "translation"
        elif "Verifying" in message: current_step = "quality_check"
        elif "Refining" in message: current_step = "refinement"
        elif "Generating" in message: current_step = "generation"
        elif "Burning" in message: current_step = "burn_in"
        
        q.put({
            "step": current_step,
            "progress": int(progress * 100),
            "message": message,
            "status": "processing"
        })
        
        # Save to global store
        jobs[job_id] = {
            "step": current_step,
            "progress": int(progress * 100),
            "message": message,
            "status": "processing"
        }

    def run_process():
        try:
            # Use the job_id from outer scope
            jobs[job_id] = {"step": "starting", "progress": 0, "message": "Initiating process...", "status": "processing"}
            
            result = translator.process(
                video_path=temp_video_path,
                source_lang=config_data.get("sourceLang"),
                target_lang=config_data.get("targetLang", "en"),
                openai_api_key=config_data.get("apiKeys", {}).get("openai"),
                openai_base_url=config_data.get("baseUrl"),
                whisper_model=config_data.get("whisperModel"),
                llm_model=config_data.get("llmModel"),
                output_dir=config_data.get("outputDir"),
                hf_token=config_data.get("apiKeys", {}).get("huggingFace"),
                use_diarization=config_data.get("enableDiarization", False),
                use_quality_check=config_data.get("qualityVerification", True),
                burn_subtitles=config_data.get("burnSubtitles", False),
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
            jobs[job_id] = completion_data
        except Exception as e:
            error_data = {
                "step": "error",
                "progress": 0,
                "message": str(e),
                "status": "error"
            }
            q.put(error_data)
            jobs[job_id] = error_data
        finally:
            q.put(None) # Sentinel
            if os.path.exists(temp_video_path):
                os.remove(temp_video_path)

    threading.Thread(target=run_process).start()

    async def event_generator():
        while True:
            # Check for new events every 100ms to keep it snappy without spinning
            try:
                event = q.get_nowait()
                if event is None:
                    break
                yield json.dumps(event) + "\n"
            except queue.Empty:
                await asyncio.sleep(0.1)

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

@app.get("/api/download")
def download_file(path: str = Query(...)):
    """
    Download endpoint for processed files.
    """
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, filename=os.path.basename(path))

@app.get("/api/job_status/{job_id}")
def get_job_status(job_id: str):
    """
    Get current status of a translation job.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

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

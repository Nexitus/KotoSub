# Video Subtitle Translator App

> [!NOTE]
> **Status:** The following vision is currently being realized. See [enhancement_plan.md](enhancement_plan.md) for current implementation progress.

## Project Vision

Create a streamlined desktop/web application that extracts audio from local video files, transcribes it in the source language (Japanese, Chinese), translates it to English, and outputs a perfectly time-coded SRT subtitle file.

**Inspired by:** KrillinAI and SoniTranslate

---

## Core Feature Set

### Phase 1: MVP (Minimum Viable Product)

#### 1. Video Input Handler
- **Accept local video files**: MP4, MKV, AVI, MOV, FLV, WebM
- **File validation**: Check file exists, readable, has audio stream
- **Audio extraction**: Use FFmpeg to extract audio track to WAV/MP3
- **Store reference**: Keep track of original video path + duration for SRT timecode mapping

#### 2. Language Selection
- **Source Language Options:**
  - Japanese (ja)
  - Chinese Simplified (zh)
  - Chinese Traditional (zh-TW)
  - *(Extensible for English, German, etc.)*

- **Target Language:**
  - English (en)
  - *(Extensible later)*

#### 3. Speech Recognition Pipeline
**Technology Choice:** Whisper (OpenAI)
- Fast, accurate, supports multiple languages
- Options:
  - **Cloud:** OpenAI Whisper API (requires API key)
  - **Local:** Faster-Whisper (offline, no API needed)
  - **Local:** Whisper.cpp (cross-platform, lightweight)

**Process:**
1. Extract audio from video
2. Split audio into chunks (if long file)
3. Transcribe each chunk to text with timestamps
4. Validate transcription confidence

#### 4. Translation Pipeline
**Technology Choice:** LLM-based translation
- **Options:**
  - OpenAI GPT API (gpt-4-turbo or gpt-3.5-turbo)
  - DeepSeek API (cost-effective alternative)
  - Locally hosted LLM (Ollama with Mistral/Llama)
  - Google Gemini API

**Process:**
1. Take transcribed text segments
2. Send to LLM with context preservation prompt
3. Preserve original timing information
4. Handle segment boundaries naturally

#### 5. Subtitle Generation
**Output Format:** SRT (SubRip)

**SRT Structure:**
```
1
00:00:01,000 --> 00:00:05,500
Translated text here

2
00:00:05,500 --> 00:00:10,000
Next translated segment

...
```

**Process:**
1. Combine transcription timing + translated text
2. Ensure no subtitle overlap
3. Merge/split subtitles for natural reading speed (~15-20 chars/sec)
4. Export as `.srt` file with same name as video

---

## Architecture

### Tech Stack

**Backend:**
- **Language:** Python 3.10+
- **Web Framework:** FastAPI or Flask (for API endpoints)
- **Video Processing:** FFmpeg (CLI), python-ffmpeg wrapper
- **Speech Recognition:** 
  - `openai-python` (for Whisper API)
  - `faster-whisper` (local)
  - `pydub` (audio manipulation)
- **Translation:** 
  - `openai` (GPT)
  - `anthropic` (Claude)
  - `langchain` (LLM abstraction layer)
- **SRT Generation:** `pysrt` library
- **Task Queue (optional):** Celery (for long-running jobs)

**Frontend:**
- **Option A:** Gradio (simple, rapid deployment like SoniTranslate)
- **Option B:** Web UI with React/Vue + FastAPI
- **Option C:** Desktop app with Electron/PyQt6

**Configuration:**
- Use `.env` file for API keys and settings
- TOML or YAML config for advanced options

---

## Data Flow

```
┌─────────────────────┐
│   Video File        │
│   (MP4, MKV, AVI)   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  FFmpeg Extract     │
│  Audio → WAV/MP3    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Whisper ASR        │
│  Audio → Text +     │
│  Timestamps         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  LLM Translation    │
│  Text → Translated  │
│  (keep timestamps)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  SRT Generator      │
│  Text + Time →      │
│  .srt file          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   Output SRT File   │
│   (timecoded)       │
└─────────────────────┘
```

---

## Implementation Roadmap

### Phase 1: Core MVP (Week 1-2)
- [ ] Video file input validation
- [ ] FFmpeg audio extraction
- [ ] Whisper transcription (cloud API)
- [ ] LLM translation integration
- [ ] SRT file generation
- [ ] CLI interface for testing

### Phase 2: UI/UX (Week 2-3)
- [ ] Gradio web interface
- [ ] File upload widget
- [ ] Language selection dropdowns
- [ ] Progress indicator
- [ ] Download SRT button
- [ ] Error handling display

### Phase 3: Optimization (Week 3-4)
- [ ] Local Whisper option (Faster-Whisper)
- [ ] Batch processing for long videos
- [ ] Subtitle timing refinement (prevent overlaps, reading speed)
- [ ] Context preservation in translation (speaker continuity)
- [ ] Caching for repeated operations

### Phase 4: Advanced Features (Week 4+)
- [ ] Multiple subtitle track output (SRT + ASS format)
- [ ] Voice speaker detection (diarization)
- [ ] Custom terminology replacement (glossary)
- [ ] Quality scoring/confidence indicators
- [ ] Subtitle editing UI before export
- [ ] Video format preset (YouTube, TikTok, etc.)
- [ ] Desktop app version

---

## Core Classes & Modules

### `VideoProcessor`
```python
class VideoProcessor:
    def validate_video(self, filepath: str) -> bool
    def extract_audio(self, video_path: str) -> str  # returns audio path
    def get_duration(self, video_path: str) -> float
```

### `TranscriptionService`
```python
class TranscriptionService:
    def transcribe(
        self, 
        audio_path: str, 
        language: str
    ) -> List[TranscriptSegment]
    
    # TranscriptSegment = {start_time, end_time, text, confidence}
```

### `TranslationService`
```python
class TranslationService:
    def translate(
        self,
        segments: List[TranscriptSegment],
        source_lang: str,
        target_lang: str
    ) -> List[TranslatedSegment]
```

### `SubtitleGenerator`
```python
class SubtitleGenerator:
    def generate_srt(
        self,
        segments: List[TranslatedSegment],
        output_path: str
    ) -> str  # returns file path
    
    def optimize_timing(
        self,
        segments: List
    ) -> List  # prevent overlaps, adjust reading speed
```

### `App` (Main Entry Point)
```python
class VideoTranslatorApp:
    def process(
        self,
        video_path: str,
        source_lang: str,
        target_lang: str = "en"
    ) -> str  # returns SRT file path
```

---

## Configuration Schema

### `.env` File
```env
# Whisper Configuration
WHISPER_PROVIDER=openai  # or local, together
OPENAI_API_KEY=sk-...
OPENAI_MODEL=whisper-1

# Translation Configuration
LLM_PROVIDER=openai  # or deepseek, anthropic, ollama
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4-turbo

# FFmpeg
FFMPEG_PATH=/usr/bin/ffmpeg  # or auto-detect

# App Settings
TEMP_DIR=/tmp/video_translator
OUTPUT_DIR=./output
MAX_FILE_SIZE_MB=2000
CHUNK_DURATION_SECONDS=300  # split long audio
```

### `config.yaml` (Advanced)
```yaml
app:
  name: VideoSubtitleTranslator
  version: 1.0.0
  port: 8000

speech_recognition:
  provider: openai  # local, openai, together
  whisper:
    model: large-v3
    language: null  # auto-detect
    temperature: 0
  
translation:
  provider: openai
  openai:
    model: gpt-4-turbo
    temperature: 0.3
  prompt_template: |
    Translate the following text from {source_lang} to {target_lang}.
    Keep the translation concise and natural for subtitle display.
    
    Text: {text}
    
    Translation:

subtitle:
  output_format: srt
  max_chars_per_line: 42
  min_duration_ms: 500
  max_gap_ms: 200  # merge subtitles if gap smaller
  
languages:
  source:
    - ja
    - zh
    - en
  target:
    - en
```

---

## Key Design Decisions

### 1. **Audio-First Approach**
- Extract audio once, reuse for all operations
- Reduces processing time vs. frame-by-frame processing
- Simpler, more reliable

### 2. **Segment-Based Translation**
- Translate transcribed segments (not raw audio)
- Preserves timing information naturally
- Easier to handle context and terminology

### 3. **SRT as Primary Output**
- Universal format (works with all video players)
- Human-readable, editable
- Easy to validate and test
- Can be converted to ASS/VTT later if needed

### 4. **Stateless Architecture**
- No database required for MVP
- Each job is independent
- Easy to scale horizontally
- Good for cloud deployment

### 5. **Local-First Option**
- Provide Faster-Whisper + local LLM option
- Users can run fully offline (after initial model download)
- No API key required
- Privacy-friendly

---

## Error Handling & Validation

### Input Validation
```
✓ File exists
✓ File is readable
✓ Video format supported
✓ Video has audio stream
✓ Duration > 0 seconds
✓ File size < MAX_SIZE
```

### Processing Errors
```
✓ Transcription failures → log + retry with different provider
✓ Translation API errors → graceful fallback
✓ Invalid language pairs → return helpful error
✓ SRT generation issues → validate timing
```

### Output Validation
```
✓ SRT file syntax valid
✓ Timecodes properly formatted
✓ No overlapping subtitles
✓ All text encoded UTF-8
```

---

## API Endpoints (FastAPI)

```python
POST /api/translate
  {
    "video_path": "/path/to/video.mp4",
    "source_language": "ja",
    "target_language": "en"
  }
  
  Returns:
  {
    "job_id": "uuid",
    "status": "processing|completed|failed",
    "output_file": "/path/to/output.srt",
    "duration_seconds": 45,
    "segment_count": 120
  }

GET /api/job/{job_id}
  Returns: status + progress

GET /api/download/{job_id}
  Returns: SRT file download

POST /api/validate
  Validate video file without processing
```

---

## Testing Strategy

### Unit Tests
- `test_video_processor.py` - FFmpeg extraction, validation
- `test_transcription.py` - Mock Whisper API
- `test_translation.py` - Mock LLM API
- `test_subtitle_generator.py` - SRT formatting, timing logic

### Integration Tests
- End-to-end workflow with test video
- Multiple language pairs
- Error scenarios (bad file, API failure)

### Test Data
- Small test videos (10-30 seconds)
- Japanese + Chinese audio samples
- Expected output files for comparison

---

## Performance Considerations

### Optimization Opportunities
1. **Audio chunking** - Process long videos in parallel chunks
2. **Caching** - Cache transcriptions per video hash
3. **Batch translation** - Send multiple segments to LLM at once
4. **Async/await** - Non-blocking API calls
5. **GPU acceleration** - Use CUDA for local Whisper

### Typical Processing Times (MVP)
- Extract audio: 10-30 seconds
- Transcribe (Cloud API): 30-60 seconds per minute of video
- Translate: 15-30 seconds per minute of video
- Generate SRT: < 1 second

**Total for 1-hour video:** ~90-120 minutes (with cloud APIs)

---

## Security Considerations

### API Key Management
- Store in environment variables, never in code
- Rotate keys regularly
- Use separate keys for dev/prod

### File Handling
- Validate file paths (no directory traversal)
- Scan uploads for malware (optional)
- Clean temp files after processing
- Limit file sizes

### User Data
- Don't log sensitive video content
- Option for local-only processing
- GDPR compliance for EU users

---

## Future Enhancements

### Near-term (Month 2-3)
- [ ] Support for more languages (Korean, Spanish, French)
- [ ] Batch file processing
- [ ] Subtitle editing UI
- [ ] Multiple output formats (ASS, VTT)
- [ ] Desktop app (PyQt6 or Tauri)

### Medium-term (Month 4-6)
- [ ] Speaker diarization (identify who's speaking)
- [ ] Custom glossary/terminology database
- [ ] Quality scoring for translations
- [ ] Video player with embedded subtitle preview
- [ ] Cloud deployment (Docker + AWS/GCP)

### Long-term (Month 6+)
- [ ] Full video dubbing (TTS synthesis)
- [ ] Voice cloning (match speaker tone)
- [ ] Multi-language simultaneous translation
- [ ] Mobile app (iOS/Android)
- [ ] Browser extension for YouTube/streaming

---

## Dependencies & Installation

### Python Packages
```
fastapi==0.104.1
uvicorn==0.24.0
pydantic==2.5.0
python-dotenv==1.0.0

# Video/Audio
ffmpeg-python==0.2.1
pydub==0.25.1
pysrt==1.1.2

# Speech Recognition
openai==1.3.9
faster-whisper==0.10.0

# Translation
langchain==0.1.1
anthropic==0.7.7

# Web UI
gradio==4.8.0

# Optional Desktop
PyQt6==6.6.1
```

### System Dependencies
- FFmpeg (audio/video processing)
- Python 3.10+
- ~4GB RAM (local Whisper model)
- GPU optional (for Faster-Whisper acceleration)

---

## Development Setup

```bash
# Clone repo
git clone <repo-url>
cd video-subtitle-translator

# Create venv
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # pytest, black, etc.

# Setup environment
cp .env.example .env
# Edit .env with your API keys

# Run tests
pytest tests/

# Start development server
python -m uvicorn app:app --reload

# Or run Gradio UI
python app_gradio.py
```

---

## File Structure

```
video-subtitle-translator/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry
│   ├── models.py            # Pydantic schemas
│   ├── processors/
│   │   ├── video.py         # VideoProcessor class
│   │   ├── transcription.py # TranscriptionService
│   │   ├── translation.py   # TranslationService
│   │   └── subtitles.py     # SubtitleGenerator
│   ├── config.py            # Configuration management
│   └── utils.py             # Helpers
├── ui/
│   ├── gradio_app.py        # Gradio interface
│   ├── static/              # CSS, JS assets
│   └── templates/           # HTML templates
├── tests/
│   ├── test_video.py
│   ├── test_transcription.py
│   ├── test_translation.py
│   ├── test_subtitles.py
│   └── fixtures/            # Test video files
├── .env.example
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── docker-compose.yml
├── README.md
└── DEVELOPMENT.md
```

---

## References & Inspiration

- **KrillinAI** (https://github.com/krillinai/KrillinAI)
  - Excellent Go-based architecture
  - Config-driven approach
  - Multi-provider support pattern

- **SoniTranslate** (https://github.com/R3gm/SoniTranslate)
  - Comprehensive Gradio UI
  - Advanced audio processing
  - Multiple TTS/STT providers
  - Good error handling

- **Related Libraries**
  - Whisper: https://github.com/openai/whisper
  - Faster-Whisper: https://github.com/guillaumekln/faster-whisper
  - pysrt: https://github.com/nitmask/pysrt
  - FFmpeg Python bindings: https://github.com/kkroening/ffmpeg-python

---

## Notes for Development

### Vibe Code Notes
- Start with Whisper API (simplest, fastest MVP)
- Use OpenAI GPT for translation initially (best quality)
- Focus on SRT output quality (timing is everything)
- Test with anime content (Japanese audio is well-segmented)
- Test with Chinese dramas (different language structure)
- Plan for subtitle merging logic (long lines should split across 2 subs)

### Potential Gotchas
1. **Subtitle timing overlap** - Last segment of sub 1 vs. first of sub 2
2. **Character encoding** - Ensure UTF-8 for CJK languages
3. **Line breaks in translation** - LLM may add newlines that break SRT format
4. **Audio extraction quality** - Some containers have multiple audio streams
5. **Language auto-detection** - Whisper sometimes confuses Japanese/Chinese

### Quick Wins
- Add subtitle preview in browser
- Show confidence scores per segment
- Allow manual adjustment before download
- Estimate processing time based on video duration
- Show example SRT in UI for reference

---

## Getting Help

If you get stuck:
1. Check example projects (KrillinAI, SoniTranslate)
2. Review Whisper docs for language codes
3. Test API keys locally before UI integration
4. Use Gradio for rapid prototyping
5. FFmpeg has great community support

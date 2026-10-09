# Context: KotoSub Live for iOS (SMB-backed)

## Problem
KotoSub's live translation currently requires sitting at the GPU PC: the web UI plays
the video and reports playback position to the FastAPI backend, which keeps a
lookahead buffer of translated subtitles. The user wants to watch NAS-hosted videos
on an iPhone with live translated subtitles, away from the PC.

## What exists today (the "core")

### Live translation engine — `app/processors/live.py`
`LiveTranslationEngine` is **player-agnostic**. It requires only:
- A heartbeat: `update_position(position, state)` where state ∈ Playing/Paused/Stopped/Disconnected
- It then maintains a translated lookahead buffer: extract audio chunk
  (`chunk_seconds=25`) ahead of `position + lookahead_seconds (30)`, transcribe via a
  whisper worker subprocess (`app/processors/whisper_worker.py`), dedup against
  existing segments, translate via local llama.cpp LLM
  (`TranslationService.translate_chunk`), append to `segments[]`, and rewrite the SRT
  atomically (`OUTPUT_DIR/<name>_live.<lang>.srt`).
- Session dies if no heartbeat for `LIVE_SESSION_TIMEOUT_SECONDS = 120`
  (`app/config.py:74`).
- Forward-seek resets the buffer; back-seek serves already-translated segments.
- MPC-HC integration (`app/processors/mpc_hc.py`) proves the engine works with a
  remote player — an iOS app is just another position reporter.

### Client contract — `frontend/components/LivePreview.tsx` (reference implementation)
1. `POST /api/live/start` with `{video_path, source_lang, target_lang,
   lookahead_seconds?, whisper_model?, llm_model?, local_llm_file?}` →
   `{session_id, video_path, duration, remuxed}` (`app/main.py:182`)
2. Play `<video src="/api/live/video/{session_id}">` (`app/main.py:286`)
3. Poll every **500ms**: `GET /api/live/status/{sid}?position=<sec>&state=<state>`
   (`app/main.py:296`). Response includes `segments[]`, `buffer_health_seconds`,
   `models_loading`, `logs[]`, `error`.
4. Stop: `POST /api/live/stop/{sid}` → returns `srt_file_path` (`app/main.py:326`)
5. Error handling: any `status.error` → stop session; 20 consecutive poll failures →
   stop session.

### Playback support
`VideoProcessor.is_browser_playable()` checks codecs; MKV etc. are **remuxed to MP4**
(lossless, `temp/remux/`) before streaming. AVPlayer cannot play MKV natively, so this
backend remux is what makes MKV sources work on iOS. Unsupported codecs → HTTP 415.

## Constraints
- faster-whisper (CUDA) + llama-cpp (GGUF, CUDA) **cannot run on iOS**. All AI
  processing stays on the GPU PC backend. The iPhone is player + remote control.
- The backend must be able to open the video file (ffmpeg audio extraction, remux).
- Personal-use distribution: sideload/TestFlight, LAN-only, plain HTTP.

## Decision record
| Decision | Choice | Rationale |
|---|---|---|
| Where does AI run? | GPU PC backend (unchanged) | On-device inference infeasible |
| Who reads the SMB share? | iOS browses natively; backend opens the same share via mapped/UNC path | User preference (Infuse-style UX); ffmpeg reads UNC paths directly on Windows |
| Playback transport | Stream from backend `/api/live/video/{sid}` | Zero new backend work; remux support; direct-SMB playback via AVAssetResourceLoader deferred to v2 |
| Scope | Live translation only | Batch/burn-in deferred |
| Distribution | Personal, SwiftUI, iOS 17+ | No App Store review; `NSAllowsLocalNetworking` ATS exception |

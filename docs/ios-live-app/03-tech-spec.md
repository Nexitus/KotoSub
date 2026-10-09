# Tech Spec: KotoSub Live for iOS

## System overview

```
iPhone (SwiftUI)                  GPU PC (FastAPI, unchanged core)        NAS (SMB)
├─ SMBService (browse)  ──SMB2─────────────────────────────────────────────►│
├─ PathMapper  smb://nas/Media/x.mkv → \\nas\Media\x.mkv
├─ KotoSubAPI ──POST /api/live/start {video_path: UNC}──► LiveTranslationEngine
├─ AVPlayer  ◄──GET /api/live/video/{sid} (Range, remuxed mp4)◄── ffmpeg/OS │◄── UNC reads
└─ Timer 500ms ──GET /api/live/status/{sid}?position&state──► segments, health
```

## Backend changes (minimal)

| # | Change | Where | Detail |
|---|---|---|---|
| B1 | Range-streaming verification | `app/main.py:286` `live_video` | Starlette ≥0.37 `FileResponse` supports `Range`. **Verify** with `curl -H "Range: bytes=0-1023"` and a player seek. If broken, add a ranged-response wrapper. |
| B2 | UNC path acceptance | `app/main.py:182` `live_start` | Already `os.path.exists(req.video_path)` — works with `\\nas\share\...`. No code change; document that the backend user needs NAS credentials (Windows Credential Manager or `net use`). |
| B3 (optional) | Bonjour advertisement | new, `main.py` | `python-zeroconf`, advertise `_kotostream._tcp.local` with port. v1 can skip. |

No new endpoints. No changes to `LiveTranslationEngine`.

## API contract (Codable mirrors of `frontend/types.ts:48-81`)

- `POST /api/live/start` → body `LiveStartRequest {video_path, source_lang="auto",
  target_lang="en", lookahead_seconds?, whisper_model?, llm_model?, local_llm_file?}`
  → `LiveStartResponse {session_id, video_path, duration, remuxed}`.
  Pass `nil` models → backend auto-selects by VRAM (`_auto_select_llm`, `main.py:168`).
- `GET /api/live/status/{sid}?position=&state=` → `LiveStatusResponse`
  (`segments: [LiveSegment {start, end, text, original, speaker?}]`,
  `buffer_health_seconds`, `models_loading`, `remuxed`, `logs: [String]`, `error`).
- `GET /api/live/video/{sid}` → video bytes (Range-capable).
- `POST /api/live/stop/{sid}` → `{srt_file_path}`.
- `GET /api/download?path=` → SRT file.
- `GET /health` → `{"status":"ok"}`.

## iOS app (SwiftUI, iOS 17+, Xcode 16)

### Module layout
```
KotoStream/
├─ App/                 KotoStreamApp.swift, AppRouter
├─ Networking/          KotoSubAPI (URLSession, async/await), APIModels (Codable)
├─ SMB/                 SMBService (async/await), SMBModels, PathMapper
├─ Persistence/         ServerStore (UserDefaults), KeychainStore (SMB creds)
├─ Features/
│  ├─ Server/           ServerSetupView (+ health check, Bonjour opt.)
│  ├─ Browser/          SMBConnectView, SMBBrowserView (file list, mapping editor)
│  ├─ Player/           PlayerView, SubtitleOverlay, BufferHealthBar,
│  │                    UpcomingSheet, LogsSheet
│  └─ Shared/           ErrorBanner, ConnectionStateView
└─ Tests/               PathMapperTests, APIModelsDecodingTests, HeartbeatTests
```

### Key behaviors

**Path mapping** (`PathMapper`, pure functions, unit-tested):
- Input: `smb://host/share/dir/file.mkv` + per-connection mapping
  `{smbRoot: "/share", backendRoot: "\\\\host\\share"}` (Windows) or POSIX mount.
- Output: backend path string. Windows UNC target: `\\host\share\dir\file.mkv`.
- Edge cases: trailing slashes, host with domain, percent-encoding, spaces.
- The mapping is validated at setup: app sends mapped path to a cheap existence
  check via `POST /api/live/start` failure mode, or a small `HEAD` on
  `/api/live/video` after start. (v1: rely on `live_start` 400 "Video file not
  found" to surface mapping errors with a friendly message.)

**Playback + heartbeat** (`PlayerView`):
- `AVPlayer` streams `/api/live/video/{sid}` over LAN HTTP.
- `addPeriodicTimeObserver` (0.5s) + `Timer` (0.5s) → `GET /api/live/status/{sid}?
  position=player.currentTime&state=Playing|Paused` (map `timeControlStatus`).
- Keep polling while session open even when Paused (engine only expires on silence,
  120s). On 20 consecutive failures: stop + explicit "Lost connection" state (mirror
  `LivePreview.tsx:74-81`).
- Subtitle overlay: binary-search / linear `segments.first { start <= t && t < end }`
  recomputed on position change; bottom-anchored, max 85% width, `.ultraThinMaterial`
  scrim. Original text toggle (show `original` on tap).
- Buffer bar: `buffer_health_seconds / lookahead` fill; colors as in web client.
- `models_loading` → persistent hint: "Press play — subtitles appear once ready."
- Stop → `POST /api/live/stop/{sid}` → offer ShareSheet with SRT fetched from
  `/api/download?path=`.

**SMB** (`SMBService`):
- SPM dependency: pure-Swift SMB2 client ("SMBClient"). Requirements: SMB2/3,
  NTLMv2 auth, directory enumeration, no write needed for v1.
  Contingency: wrap `libsmb2` via a small C target if the package blocks on a
  needed capability.
- Credentials in Keychain (`kSecAttrAccessibleAfterFirstUnlock`).
- Browse UI: breadcrumb directories, sort folders-first, filter to
  `mp4|mkv|mov|avi|webm` (+ size/date columns), no recursion in v1.

**Networking/ATS**:
- `NSAppTransportSecurity → NSAllowsLocalNetworking = YES`.
- `NSLocalNetworkUsageDescription` (+ `NSBonjourServices` if B3 done).
- Timeouts: connect 5s, status poll 5s, video request default.

### Error taxonomy (human-readable, mirroring web `describeError`)
`file not found` → mapping/credential hint; `415` → codec message;
`ffmpeg` → backend install message; poll exhaustion → "Lost connection to backend".

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| SMBClient package gaps (auth dialects, signing) | Med | Evaluate first (SMB2 against the actual NAS); libsmb2 fallback |
| Backend can't open UNC (creds) | Med | Setup doc: Credential Manager entry; verified during connection test |
| Backgrounded app >120s kills session | High by design | v1 foreground-only; note in UI; v2 Background audio |
| Range streaming regression | Low | B1 verification step |
| iOS LAN HTTP prompts | Low | Documented entitlements; first-run explainer |

## Milestones
1. **Backend touch-up** — B1 test; optional B3. *(0.5d)*
2. **iOS skeleton** — project, ServerSetup + `/health`, API layer + Codable tests. *(1d)*
3. **SMB** — SMBService, browser UI, PathMapper + unit tests, Keychain. *(2-3d)*
4. **Live session** — start/stop, AVPlayer, heartbeat, overlay, buffer UI. *(2-3d)*
5. **Polish** — error taxonomy, logs viewer, upcoming sheet, saved connections, SRT share. *(1-2d)*

## Verification checklist (for Codex review)
- [ ] Contract in spec matches `app/main.py` exactly (params, defaults, status fields)
- [ ] Heartbeat cadence/state mapping can't trip `LIVE_SESSION_TIMEOUT_SECONDS=120`
- [ ] PathMapper handles Windows UNC + POSIX mount targets, slashes, encoding
- [ ] MKV path exercised via remux (`remuxed: true` in response)
- [ ] No secrets in code/logs; Keychain only

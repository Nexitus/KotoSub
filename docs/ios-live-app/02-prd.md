# PRD: KotoSub Live for iOS

## Users
Single user (project owner): content creator with a NAS (SMB), a GPU PC running
KotoSub, and an iPhone/iPad. Watches foreign-language video from the couch with
live translated subtitles.

## Value
Watch any video on the NAS with live AI subtitles, without being at the PC,
without pre-processing files.

## Goals (v1)
1. Browse and play SMB-hosted videos from iPhone with live translated subtitles.
2. Same latency profile as the web live preview (30s lookahead default).
3. Zero backend workflow changes: start/stop sessions from the phone.

## Non-goals (v1)
- Batch translation / burn-in jobs
- On-device AI inference
- Direct-from-NAS playback (v2 candidate: AVAssetResourceLoader + SMB streamer)
- App Store distribution, HTTPS
- Multiple simultaneous sessions

## User stories
1. **Setup**: As a user, I enter my backend host:port once and see a connected
   confirmation (GET /health). Credentials for SMB are stored in Keychain.
2. **Browse**: As a user, I connect to my NAS (host, share, user, password), map the
   SMB root to the backend-visible path once per share, and browse a filtered list of
   video files (mp4/mkv/mov/avi/webm).
3. **Watch**: As a user, I tap a video; models load on the backend (~status shows
   "Loading AI models"); I press play immediately; translated subtitles overlay the
   video as I watch.
4. **Trust the buffer**: As a user, I see buffer health (seconds translated ahead of
   my position, color-coded green ≥15s / yellow ≥5s / red below) and upcoming lines.
5. **Seek**: If I seek forward past the buffer, translation resets to my new position.
6. **Leave with the goods**: As a user, when I stop the session I can download the
   generated SRT.
7. **Failure is explicit**: Backend unreachable, model load failure, unsupported
   codec (415), or SMB errors all surface a human-readable message; status is never
   ambiguous (idle / connecting / loading models / ready / failed).

## Success criteria
- MKV and MP4 from the NAS play with live subtitles within ~45s of tapping the file
  (model load + first chunk).
- A 10-minute viewing session with seeks and pauses holds >95% subtitle continuity.
- App regains usable state after backend restart (session loss is explicit, not silent).

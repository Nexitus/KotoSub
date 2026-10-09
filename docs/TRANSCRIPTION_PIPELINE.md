# Transcription Pipeline Reference

> Keep this document updated whenever the transcription or audio pre-processing
> pipeline changes. It is the design contract and decision log for everything
> between "video file" and "translated subtitle segments."
> Any future edit to `app/processors/video.py`, `app/processors/transcription.py`,
> or the `AUDIO_*` / `WHISPER_*` / `QWEN_*` / `VAD_*` settings updates this file first.

## Pipeline diagram

```
video file
  ├─ 1. probe_audio_quality()        (video.py)  → noisy/clean decision, ~1s
  ├─ 2. extract_audio()              (video.py)  → 16kHz mono WAV
  │       highpass 100Hz + loudnorm   — always
  │       afftdn + acompressor        — only when preset says "noisy"
  ├─ 3. Engine selection (transcription.py:select_transcription_class)
  │       Whisper ids (default)      → TranscriptionService (faster-whisper)
  │       "Qwen/Qwen3-ASR-*" ids     → QwenTranscriptionService (qwen-asr)
  ├─ 4. Silence detection (vad.py, Silero VAD via faster-whisper)
  │       a. speech regions; regions ≤ QWEN_MAX_WINDOW_SECONDS
  │       b. Qwen: windows are the only thing transcoded to the model
  │       c. live: a fully silent chunk returns [] with NO model call
  ├─ 5. Whisper path (TranscriptionService.transcribe)
  │       a. main pass: beam 5, VAD, hallucination controls
  │       b. audit: per-segment triggers → retry_regions
  │            - avg_logprob < WHISPER_RETRY_LOGPROB
  │            - repetition loop detected (_is_repetition_loop)
  │            - compression_ratio > WHISPER_COMPRESSION_RATIO_THRESHOLD
  │       c. hallucination suspects (no_speech_prob > 0.9 AND short text)
  │          are DROPPED, not retried — VAD says there was no speech there
  │       d. retry pass over failed regions: wider beam + temperature
  │          fallbacks + patience
  │       e. merge retry output, sort by start; drop list recorded
  ├─ 5'. Qwen path (qwen_asr.py, optional dependency: `pip install qwen-asr`)
  │       a. ASR model Qwen/Qwen3-ASR-1.7B (bf16 on CUDA, fp32 on CPU)
  │       b. word timestamps from Qwen/Qwen3-ForcedAligner-0.6B
  │       c. aligner supports 11 languages (zh/en/yue/fr/de/it/ja/ko/pt/ru/es);
  │          others transcribe with window-boundary timing + a printed notice
  │       d. unsupported ISO codes fail LOUDLY before any model call
  │       e. words → subtitle segments on sentence punctuation, gaps >
  │          QWEN_SEGMENT_GAP_SECONDS, or QWEN_MAX_SEGMENT_SECONDS length;
  │          CJK text joins without spaces, Latin with spaces
  │       f. no retry tier (no logprob/compression signals); segment
  │          metadata mirrors the Whisper dict shape (start/end/text/
  │          speaker/avg_logprob/words) so diarization, translation,
  │          refinement and generation are engine-agnostic
  ├─ 6. diarization (optional, pyannote)
  ├─ 7. LLM translation + quality check
  └─ 8. subtitle refinement (CPS split, timing polish)
```

## Tunable knobs

All settings live in `app/config.py` and are overridable via `.env`
(no per-job UI override by design — batch verifiability beats per-job fiddling).

| Setting | Default | Where used | What it does / failure mode when wrong |
|---|---|---|---|
| `AUDIO_ENHANCE` | `auto` | `video.py:extract_audio` | `auto`/`on`/`off`. `auto` runs the probe; noisy audio gets afftdn denoise + acompressor. `on` forces the filter chain, `off` is the old clean behavior. Wrong set to `on` on clean music: vocals dull. |
| `AUDIO_PROBE_NOISE_FLOOR_DB` | `-45.0` | `video.py` | Noise floor (dBFS, louder=higher) above which audio counts as noisy. Too high → denoise triggers on decent audio; too low → real noise gets through. |
| `WHISPER_WORD_TIMESTAMPS` | `True` | whisper kwargs | Word-level timing for split/fix tools. Disabling degrades subtitle timing polish. |
| `WHISPER_CONDITION_ON_PREVIOUS_TEXT` | `False` | whisper kwargs | Conditioning reduces repetition risk drift but coils hallucinations across segments (YATSEE: leave off). Turning on causes runaway context errors on noisy audio. |
| `WHISPER_NO_SPEECH_THRESHOLD` | `0.6` | whisper kwargs | faster-whisper's own no-speech gate. Lower → more "silent" words kept, more boilerplate. |
| `WHISPER_LOG_PROB_THRESHOLD` | `-1.0` | whisper kwargs | faster-whisper drops segments whose logprob is worse. Too tight (-0.5) on accents; too loose (-2) keeps garbage. |
| `WHISPER_COMPRESSION_RATIO_THRESHOLD` | `2.4` | whisper kwargs + audit | Whisper's own repetition trigger; also used as detector input in audit pass. |
| `WHISPER_SPEECH_PAD_MS` | `100` | VAD params | Padding around speech regions; larger pads help word onsets but bleed noise into segments. |
| `WHISPER_NO_SPEECH_DROP_PROB` | `0.9` | audit in transcribe() | VAD confidence above which short segments are dropped as hallucinated boilerplate. |
| `WHISPER_HALLUCINATION_MAX_CHARS` | `32` | audit in transcribe() | Max text length eligible for the hallucination-drop rule. Too large deletes real short lines. |
| `WHISPER_RETRY_LOGPROB` | `-0.8` | audit in transcribe() | Confidence below which a segment's region is queued for wide-beam retrial. |
| `WHISPER_RETRY_BEAM_SIZE` | `10` | retry pass | Beam width for the retry pass. Higher = slower + safer. |
| `WHISPER_RETRY_TEMPERATURE` | `"0.0,0.2,0.4,0.6,0.8,1.0"` | retry pass | Comma list; retry pass tries these temp values, weighted by faster-whisper internals. |
| `WHISPER_RETRY_PATIENCE` | `2.0` | retry pass | Retry-pass decoding patience (faster-whisper param). |
| `WHISPER_LOOP_OVERLAP_THRESHOLD` | `0.6` | `_is_repetition_loop` | Token 3-gram overlap fraction across consecutive segments above which it's a loop. Too low → harmless repetition retried. |
| `QWEN_ASR_MODEL` | `Qwen/Qwen3-ASR-1.7B` | qwen_asr.py | ASR weights used when the frontend selects the Qwen engine. Listed in the transcription selector via `/api/models`. |
| `QWEN_ASR_ALIGNER_MODEL` | `Qwen/Qwen3-ForcedAligner-0.6B` | qwen_asr.py | Forced-aligner weights; word timestamps come from it. Removing the aligner config kills word timing (window-bound fallback). |
| `QWEN_ASR_MAX_NEW_TOKENS` / `QWEN_ASR_MAX_BATCH` | `256` / `8` | qwen_asr.py | Decoder cap per window (28s speech ≪ 256 tokens; raise only for pathological content) and windows per transcribe call. Batch too high → OOM on small GPUs. |
| `QWEN_MAX_WINDOW_SECONDS` | `28.0` | vad.py + qwen_asr.py | Max transcription window. Chosen under the aligner's 5-minute ceiling with headroom; silence gaps inside a window are kept as-is (adjusting boundaries at hard gaps). |
| `QWEN_SEGMENT_GAP_SECONDS` / `QWEN_MAX_SEGMENT_SECONDS` | `0.8` / `6.0` | `_group_words` | Word gap or segment length that starts a new subtitle segment. Gap too small → choppy lines; too large → walls of text. |
| `VAD_MIN_SPEECH_MS` / `VAD_MIN_SILENCE_MS` | `250` / `500` | vad.py | Silero gate: regions shorter than min-speech are discarded, silence ≥ min-silence splits regions. Aggressive values skip real quiet speech. |
| `VAD_SPEECH_PAD_MS` | `200` | vad.py | Padding added to each speech region so word onsets near region boundaries aren't lost. |

## Silence detection (audio detection scope)

Speech regions come from faster-whisper's vendored Silero VAD (`vad.py`) so no
new dependency is introduced. Invariants:

1. **Silence is never decoded.** The Qwen engine transcribes only speech
   windows; the live pipeline checks each extracted chunk and skips the model
   entirely when the VAD finds no speech. The Whisper engine has its own
   internal `vad_filter=True` (quota unchanged).
2. **VAD failure degrades, never breaks.** `get_speech_regions` returns `None`
   on unavailable/failed VAD; callers then treat the whole track as speech
   (feature off, original behavior). Tests cover the skip and meta paths.
3. **Omission is reported in meta**, e.g. Qwen meta carries
   `silence_skipped_seconds` and window counts; live logs emit an explicit
   "silent chunk — skipped" line instead of a silent gap.

## Doctrine: retranscribe, never repair

Whisper on poor sources fails in predictable ways — boilerplate on music/silence
("Thank you.", "Bye."), and repetition loops (same 3-gram chain across
consecutive segments). Do **not** clean these with the LLM; the LLM happily
invents plausible text from garbage (YATSEE documentation's explicit warning).
Instead, collect the region boundaries and re-run faster-whisper on those clips
with a wider beam, temperature fallbacks and patience. That is the two-tier
pass in `transcribe()`. Only pure audit logic may decide a segment is bad —
never a heuristic text-based "fix."

## Dropped-cue transparency

Any segment dropped by the audit-level rules (no_speech/suspicion) is collected
in a `dropped` list and (a) logged in one line to stdout (which the frontend
already streams into Live Logs), and (b) returned to `core.py` inside the
metadata tuple for possible future surfacing. It should never be silently gone:
the operator can re-check the original timestamp against the video manually.

## Why the retry pass exists (historical)

Whisper/faster-whisper, on noisy/short/unclear audio, sometimes dedicates full
confidence to the wrong reading. Retrying that narrow region (using
`clip_timestamps`) with a wider beam + temperature ladder re-decodes from the
same audio but anneals differently — usually yielding a better read. It was
built for low-logprob flags, later extended to repetition loops and
compression_ratio outliers because the logprob gate kept under-tripping on the
most common failure mode (loops where per-segment confidence stays decent).

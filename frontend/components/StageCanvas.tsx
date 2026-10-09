import React, { useEffect, useState } from 'react';
import Hls from 'hls.js';
import { ProcessingStep, LiveStatusResponse } from '../types';
import { ICONS } from '../constants';
import DropZone from './DropZone';

export type StageMode = 'empty' | 'preview' | 'processing' | 'done' | 'live';

interface LiveSegmentData {
  original: string;
  text: string;
  speaker: string | null;
}

interface StageCanvasProps {
  mode: StageMode;
  file: File | null;
  previewUrl: string | null;
  resultUrl: string | null;
  steps: ProcessingStep[];
  latestLog: string | null;
  liveSegment?: LiveSegmentData | null;
  sessionId?: string | null;
  liveStatus?: LiveStatusResponse | null;
  videoRef?: React.RefObject<HTMLVideoElement | null>;
  onLiveTimeUpdate?: () => void;
  onLiveError?: () => void;
  onLiveRecover?: () => void;
  onFile: (f: File) => void;
  onRemove: () => void;
}

const StageCanvas: React.FC<StageCanvasProps> = ({
  mode,
  file,
  previewUrl,
  resultUrl,
  steps,
  latestLog,
  liveSegment,
  sessionId,
  liveStatus,
  videoRef,
  onLiveTimeUpdate,
  onLiveError,
  onLiveRecover,
  onFile,
  onRemove,
}) => {
  const activeStep = steps.find(s => s.status === 'processing') ?? null;

  const skip = (v: HTMLVideoElement | null, delta: number) => {
    if (!v || !v.duration) return;
    v.currentTime = Math.min(Math.max(v.currentTime + delta, 0), v.duration);
  };

  // Match the frame to the video's real shape (clamped so 9:16 / 21:9 still fit the page)
  const [aspect, setAspect] = useState<number | null>(null);
  useEffect(() => { setAspect(null); }, [previewUrl, resultUrl, sessionId]);
  const handleMetadata = (e: React.SyntheticEvent<HTMLVideoElement>) => {
    const v = e.currentTarget;
    if (v.videoWidth && v.videoHeight) setAspect(v.videoWidth / v.videoHeight);
    onLiveRecover?.();
  };
  // Cache-bust the live stream when the backend flips out of transcoding, so the
  // <video> always refetches the actual playable file instead of a cached failure.
  const [sourceV, setSourceV] = useState<number | null>(null);
  useEffect(() => { setSourceV(null); }, [sessionId]);
  useEffect(() => {
    if (sessionId && liveStatus && !liveStatus.transcoding) setSourceV(Date.now());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, liveStatus?.transcoding]);

  // HLS event stream: attach hls.js once the playlist exists (Safari plays natively).
  // If the attach fails while the playlist is still growing (e.g. loaded in the
  // gap before the first segment flushes), retry a few times before giving up.
  const [hlsRetry, setHlsRetry] = useState(0);
  useEffect(() => { setHlsRetry(0); }, [sessionId]);
  useEffect(() => {
    if (mode !== 'live' || !sessionId || !liveStatus?.hls || !liveStatus?.playlist_ready) return;
    const v = videoRef?.current;
    if (!v) return;
    const url = `/api/live/hls/${sessionId}/playlist.m3u8`;
    let hls: Hls | null = null;
    if (v.canPlayType('application/vnd.apple.mpegurl')) {
      v.src = url;
    } else if (Hls.isSupported()) {
      hls = new Hls({ liveDurationInfinity: true, backBufferLength: 90 });
      hls.on(Hls.Events.ERROR, (_evt, data) => {
        if (!data.fatal || !hls) return;
        if (hlsRetry < 3) {
          hls.destroy();
          setHlsRetry(hlsRetry + 1);
        } else {
          onLiveError?.();
        }
      });
      hls.loadSource(url);
      hls.attachMedia(v);
    } else {
      onLiveError?.();
      return;
    }
    return () => { if (hls) hls.destroy(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, sessionId, liveStatus?.hls, liveStatus?.playlist_ready, hlsRetry]);
  const clamped = aspect ? Math.min(Math.max(aspect, 9 / 16), 21 / 9) : null;
  const overall = Math.min(
    100,
    Math.round(steps.reduce((acc, s) => acc + s.progress, 0) / Math.max(steps.length, 1))
  );
  const doneWithoutVideo = mode === 'done' && !resultUrl;

  return (
    <div
      className={`relative w-full rounded-2xl overflow-hidden border border-edge shadow-lg mx-auto ${
        mode === 'empty' ? 'bg-raised' : 'bg-stage'
      } ${clamped ? '' : 'aspect-video'}`}
      style={clamped ? { aspectRatio: `${clamped}`, maxHeight: '70vh', maxWidth: '100%' } : undefined}
    >
      {mode === 'empty' && (
        <div className="absolute inset-6 md:inset-10">
          <DropZone
            id="stage-upload"
            onFile={onFile}
            hint="MP4, MOV, MKV, AVI, WebM — processed locally on your machine"
          />
        </div>
      )}

      {mode !== 'empty' && mode !== 'live' && (mode !== 'done' || resultUrl) && (
        <video
          src={mode === 'done' ? (resultUrl ?? undefined) : (previewUrl ?? undefined)}
          controls={mode !== 'processing'}
          onLoadedMetadata={handleMetadata}
          className={`w-full h-full object-contain bg-black ${
            mode === 'processing' ? 'brightness-[0.35] saturate-[0.8]' : ''
          }`}
        />
      )}

      {mode === 'live' && sessionId && (!liveStatus || (liveStatus.hls && !liveStatus.playlist_ready) ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 text-center px-6 enter-slide-up">
          {!liveStatus?.transcode_error && (
            <span
              className="h-10 w-10 rounded-full border-[3px] border-brand border-t-transparent animate-spin"
              aria-hidden="true"
            />
          )}
          <div>
            {liveStatus?.transcode_error ? (
              <>
                <p className="text-white text-lg font-semibold">Couldn't convert this video</p>
                <p className="text-white/60 text-sm mt-1 max-w-sm">
                  {liveStatus.transcode_error}. You can still watch the subtitles appear in the panel below, or try a smaller/different file.
                </p>
              </>
            ) : (
              <>
                <p className="text-white text-lg font-semibold">Preparing video for playback</p>
                <p className="text-white/60 text-sm mt-1 max-w-sm">
                  This file's codec (e.g. HEVC) can't play in browsers — converting to H.264 once. Large files can take a few minutes.
                </p>
              </>
            )}
          </div>
          {!liveStatus?.transcode_error && (
            <div className="w-56">
              <div className="h-1.5 bg-white/15 rounded-full overflow-hidden">
                <div
                  className="h-full bg-brand rounded-full transition-all duration-500"
                  style={{ width: `${liveStatus?.transcode_progress ?? 0}%` }}
                />
              </div>
              <p className="text-white/70 text-xs mt-2 tabular-nums" aria-live="polite">
                {Math.round(liveStatus?.transcode_progress ?? 0)}%
              </p>
            </div>
          )}
        </div>
      ) : (
        <>
          {liveStatus?.hls ? (
            <video
              ref={videoRef}
              controls
              onLoadedMetadata={handleMetadata}
              className="w-full h-full object-contain bg-black"
              onTimeUpdate={onLiveTimeUpdate}
            />
          ) : (
            <video
              ref={videoRef}
              src={`/api/live/video/${sessionId}${sourceV ? `?t=${sourceV}` : ''}`}
              controls
              onLoadedMetadata={handleMetadata}
              className="w-full h-full object-contain bg-black"
              onTimeUpdate={onLiveTimeUpdate}
              onError={onLiveError}
            />
          )}
          <div className="absolute inset-y-0 left-3 right-3 z-0 flex items-center justify-between pointer-events-none">
            <button
              onClick={() => skip(videoRef?.current ?? null, -10)}
              aria-label="Back 10 seconds"
              className="pointer-events-auto p-2.5 rounded-full bg-black/45 hover:bg-black/70 text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M11 6 5 12l6 6M19 6l-6 6 6 6" />
              </svg>
              <span className="sr-only">-10s</span>
            </button>
            <button
              onClick={() => skip(videoRef?.current ?? null, 10)}
              aria-label="Forward 10 seconds"
              className="pointer-events-auto p-2.5 rounded-full bg-black/45 hover:bg-black/70 text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth={1.8} viewBox="0 0 24 24" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 6l6 6-6 6M5 6l6 6-6 6" />
              </svg>
              <span className="sr-only">+10s</span>
            </button>
          </div>
        </>
      ))}

      {mode === 'preview' && file && (
        <div className="absolute top-4 left-4 flex items-center gap-2 px-3 py-1.5 bg-black/60 backdrop-blur-sm rounded-full text-white text-xs font-medium max-w-[80%]">
          <ICONS.Video />
          <span className="truncate">{file.name}</span>
          <span className="text-white/60 shrink-0">{(file.size / (1024 * 1024)).toFixed(0)} MB</span>
          <button
            onClick={onRemove}
            aria-label="Remove video"
            className="shrink-0 -mr-1 w-5 h-5 rounded-full hover:bg-white/20 text-white/70 hover:text-white text-sm leading-none focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-white"
          >
            ×
          </button>
        </div>
      )}

      {mode === 'live' && sessionId && (
        <div className="absolute top-4 left-4 z-10 flex items-center gap-2 px-3 py-1.5 bg-black/60 backdrop-blur-sm rounded-full text-white text-xs font-medium">
          <span className="w-2 h-2 rounded-full bg-error animate-pulse shrink-0" aria-hidden="true" />
          <span className="font-semibold">Live</span>
          {file && <span className="text-white/60 truncate max-w-[180px]">{file.name}</span>}
          <button
            onClick={onRemove}
            aria-label="Stop session and remove video"
            className="shrink-0 -mr-1 w-5 h-5 rounded-full hover:bg-white/20 text-white/70 hover:text-white text-sm leading-none focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-white"
          >
            ×
          </button>
        </div>
      )}

      {mode === 'processing' && (
        <>
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-0 h-24 top-0 bg-gradient-to-b from-transparent via-brand/25 to-transparent stage-scan"
          />
          <div className="pointer-events-none absolute inset-0 bg-stage/40 flex flex-col items-center justify-center gap-4 text-center px-6">
            <span
              className="h-10 w-10 rounded-full border-[3px] border-brand border-t-transparent animate-spin"
              aria-hidden="true"
            />
            <p className="text-white text-lg font-semibold enter-slide-up" key={activeStep?.id}>
              {activeStep ? activeStep.label : 'Preparing…'}
            </p>
            <p className="text-white/70 text-sm font-medium" aria-hidden="true">
              {overall}%
            </p>
          </div>
          {latestLog && (
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 max-w-[85%] px-4 py-2 bg-black/70 backdrop-blur-sm rounded-lg text-white/90 text-sm font-medium truncate pointer-events-none select-none">
              {latestLog}
            </div>
          )}
        </>
      )}

      {(mode === 'processing' || mode === 'live') && liveSegment && (
        <div className="pointer-events-none absolute inset-x-0 bottom-16 flex flex-col items-center gap-1.5 px-8 enter-slide-up" key={liveSegment.text}>
          {mode === 'processing' && liveSegment.speaker && (
            <p className="text-white/50 text-xs font-semibold uppercase tracking-wider">{liveSegment.speaker}</p>
          )}
          {mode === 'processing' && (
            <p className="max-w-[85%] text-white/70 text-sm truncate">{liveSegment.original}</p>
          )}
          <p className="max-w-[85%] px-4 py-2 bg-black/70 backdrop-blur-sm rounded-lg text-white text-lg font-semibold text-center leading-snug">
            {liveSegment.text}
          </p>
        </div>
      )}

      {doneWithoutVideo && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 text-center px-6 enter-slide-up">
          <div className="p-4 rounded-full bg-success/15 text-success">
            <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <p className="text-white text-xl font-bold">Subtitles ready</p>
          <p className="text-white/60 text-sm">Grab your files from the panel on the right.</p>
        </div>
      )}
    </div>
  );
};

export default StageCanvas;

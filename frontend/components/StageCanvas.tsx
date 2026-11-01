import React, { useEffect, useState } from 'react';
import Hls from 'hls.js';
import { ChevronsLeft, ChevronsRight, CircleCheck, Video, X } from 'lucide-react';
import { ProcessingStep, LiveStatusResponse } from '../types';
import AITextLoading from '@/components/kokonutui/ai-text-loading';
import Loader from '@/components/kokonutui/loader';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';

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
      className={`relative w-full rounded-2xl overflow-hidden border border-border shadow-lg mx-auto ${
        mode === 'empty' ? 'bg-card' : 'bg-stage'
      } ${clamped ? '' : 'aspect-video'}`}
      style={clamped ? { aspectRatio: `${clamped}`, maxHeight: '70vh', maxWidth: '100%' } : undefined}
    >
      {mode === 'empty' && (
        <div className="absolute inset-6 md:inset-10">
          <UploadZone onFile={onFile} />
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
        <div className="dark absolute inset-0 flex flex-col items-center justify-center gap-4 text-center px-6 enter-slide-up">
          {liveStatus?.transcode_error ? (
            <div>
              <p className="text-white text-lg font-semibold">Couldn't convert this video</p>
              <p className="text-white/60 text-sm mt-1 max-w-sm">
                {liveStatus.transcode_error}. You can still watch the subtitles appear in the panel below, or try a smaller/different file.
              </p>
            </div>
          ) : (
            <>
              <Loader
                size="sm"
                className="gap-4 p-0"
                title="Preparing video for playback"
                subtitle="This file's codec (e.g. HEVC) can't play in browsers — converting to H.264 once. Large files can take a few minutes."
              />
              <div className="w-56">
                <Progress
                  value={liveStatus?.transcode_progress ?? 0}
                  className="h-1.5 bg-white/15 [&_[data-slot=progress-indicator]]:bg-white"
                />
                <p className="text-white/70 text-xs mt-2 tabular-nums" aria-live="polite">
                  {Math.round(liveStatus?.transcode_progress ?? 0)}%
                </p>
              </div>
            </>
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
            <Button
              variant="ghost"
              size="icon"
              onClick={() => skip(videoRef?.current ?? null, -10)}
              aria-label="Back 10 seconds"
              className="pointer-events-auto rounded-full bg-black/45 text-white hover:bg-black/70 hover:text-white"
            >
              <ChevronsLeft className="size-5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => skip(videoRef?.current ?? null, 10)}
              aria-label="Forward 10 seconds"
              className="pointer-events-auto rounded-full bg-black/45 text-white hover:bg-black/70 hover:text-white"
            >
              <ChevronsRight className="size-5" />
            </Button>
          </div>
        </>
      ))}

      {mode === 'preview' && file && (
        <div className="absolute top-4 left-4 flex items-center gap-2 px-3 py-1.5 bg-black/60 backdrop-blur-sm rounded-full text-white text-xs font-medium max-w-[80%]">
          <Video className="size-4 shrink-0" />
          <span className="truncate">{file.name}</span>
          <span className="text-white/60 shrink-0">{(file.size / (1024 * 1024)).toFixed(0)} MB</span>
          <Button
            variant="ghost"
            size="icon"
            onClick={onRemove}
            aria-label="Remove video"
            className="-mr-1 size-5 rounded-full text-white/70 hover:bg-white/20 hover:text-white"
          >
            <X className="size-3.5" />
          </Button>
        </div>
      )}

      {mode === 'live' && sessionId && (
        <div className="absolute top-4 left-4 z-10 flex items-center gap-2 px-3 py-1.5 bg-black/60 backdrop-blur-sm rounded-full text-white text-xs font-medium">
          <span className="w-2 h-2 rounded-full bg-destructive animate-pulse shrink-0" aria-hidden="true" />
          <span className="font-semibold">Live</span>
          {file && <span className="text-white/60 truncate max-w-[180px]">{file.name}</span>}
          <Button
            variant="ghost"
            size="icon"
            onClick={onRemove}
            aria-label="Stop session and remove video"
            className="-mr-1 size-5 rounded-full text-white/70 hover:bg-white/20 hover:text-white"
          >
            <X className="size-3.5" />
          </Button>
        </div>
      )}

      {mode === 'processing' && (
        <>
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-0 h-24 top-0 bg-gradient-to-b from-transparent via-brand/25 to-transparent stage-scan"
          />
          <div
            aria-hidden="true"
            className="dark pointer-events-none absolute inset-0 bg-stage/40 flex flex-col items-center justify-center gap-4 text-center px-6"
          >
            <Loader size="sm" title="" subtitle="" className="gap-0 p-0" />
            <AITextLoading
              key={activeStep?.id ?? 'prep'}
              texts={[activeStep?.label ?? 'Preparing…']}
              label={activeStep?.label ?? 'Preparing'}
              className="text-lg font-semibold"
            />
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
            <CircleCheck className="size-10" aria-hidden="true" />
          </div>
          <p className="text-white text-xl font-bold">Subtitles ready</p>
          <p className="text-white/60 text-sm">Grab your files from the panel on the right.</p>
        </div>
      )}
    </div>
  );
};

export default StageCanvas;

function UploadZone({ onFile }: { onFile: (f: File) => void }) {
  const [isDragging, setIsDragging] = useState(false);

  const acceptFile = (f: File) => {
    if (f.type.startsWith('video/') || /\.(mp4|mov|mkv|avi|webm)$/i.test(f.name)) {
      onFile(f);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) acceptFile(e.target.files[0]);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setIsDragging(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) acceptFile(dropped);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      document.getElementById('stage-upload')?.click();
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Upload video file. Press Enter or Space to browse, or drag and drop a file here."
      onClick={() => document.getElementById('stage-upload')?.click()}
      onKeyDown={handleKeyDown}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={cn(
        'w-full h-full border-2 border-dashed rounded-2xl transition-all flex flex-col items-center justify-center text-center cursor-pointer focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 py-16 md:py-24 px-8 space-y-5',
        isDragging ? 'border-brand bg-accent' : 'border-input hover:border-brand/60 hover:bg-accent/50'
      )}
    >
      <input type="file" id="stage-upload" className="hidden" accept="video/*" onChange={handleFileChange} />
      <div className="p-4 rounded-full bg-muted text-muted-foreground flex items-center justify-center transition-colors">
        <Video className="size-9" />
      </div>
      <div>
        <p className="font-semibold text-foreground text-lg">Drop your video here</p>
        <p className="text-sm text-muted-foreground mt-1">MP4, MOV, MKV, AVI, WebM — processed locally on your machine</p>
      </div>
    </div>
  );
}

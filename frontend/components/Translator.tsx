import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowRight, Check, Circle, Download, Loader2, XCircle, type LucideIcon } from 'lucide-react';
import { AppSettings, SubtitleConfig, ProcessingStep, LiveStartResponse, LiveStatusResponse } from '../types';
import { SOURCE_LANGUAGES, LOOKAHEAD_PRESETS } from '../constants';
import { api } from '../services/api';
import StageCanvas, { StageMode } from './StageCanvas';
import OptionsDrawer from './OptionsDrawer';
import ResultsPanel from './ResultsPanel';
import LogsConsole from './LogsConsole';
import Card from './Card';
import Banner from './ui/Banner';
import FormLabel from './ui/FormLabel';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';

interface TranslatorProps {
  settings: AppSettings;
  isProcessing: boolean;
  steps: ProcessingStep[];
  logs: string[];
  result: any;
  error: string | null;
  startedAt: number | null;
  liveSegment: { original: string; text: string; speaker: string | null } | null;
  onStart: (file: File, config: SubtitleConfig) => void;
  onReset: () => void;
}

const CONFIG_KEY = 'kotosub_translator_config_v1';

const formatTime = (sec: number) => {
  if (!isFinite(sec)) return '0:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
};

const describeError = (raw: string): string => {
  const lower = raw.toLowerCase();
  if (lower.includes('already using the gpu')) {
    return 'The GPU is busy with another job. Only one translation runs at a time — wait for it to finish, then try again.';
  }
  if (lower.includes('still stopping')) {
    return 'The previous live session is still stopping. Try again in a moment.';
  }
  if (lower.includes('file not found')) return 'Video file not found. Check the path and try again.';
  if (lower.includes('ffmpeg')) return 'FFmpeg is required but could not run. Check the backend installation.';
  if (lower.includes('codec')) return 'The video codec is not supported for in-browser playback.';
  if (lower.includes('permission denied') || lower.includes('access denied')) return 'Access to the video file was denied.';
  return raw;
};

const formatDuration = (ms: number) => {
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  return `${m}m ${s.toString().padStart(2, '0')}s`;
};

const STEP_ICON: Record<ProcessingStep['status'], LucideIcon> = {
  idle: Circle,
  processing: Loader2,
  completed: Check,
  error: XCircle,
};

const STEP_LABEL_COLORS: Record<ProcessingStep['status'], string> = {
  completed: 'text-success',
  error: 'text-destructive',
  processing: 'text-brand',
  idle: 'text-muted-foreground',
};

const STEP_FILLS: Record<ProcessingStep['status'], string> = {
  completed: '[&_[data-slot=progress-indicator]]:bg-success',
  error: '[&_[data-slot=progress-indicator]]:bg-destructive',
  processing: '[&_[data-slot=progress-indicator]]:bg-brand',
  idle: '[&_[data-slot=progress-indicator]]:bg-muted-foreground',
};

interface PipelineProps {
  steps: ProcessingStep[];
  startedAt: number | null;
  endedAt: number | null;
  failed: boolean;
}

const Pipeline: React.FC<PipelineProps> = ({ steps, startedAt, endedAt, failed }) => {
  const [now, setNow] = useState(() => Date.now());
  const running = startedAt !== null && endedAt === null;

  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [running]);

  const anyError = failed || steps.some(s => s.status === 'error');
  const allDone = steps.every(s => s.status === 'completed');
  const overallStatus: ProcessingStep['status'] = anyError ? 'error' : allDone ? 'completed' : 'processing';
  const overall = Math.min(
    100,
    Math.round(steps.reduce((acc, s) => acc + s.progress, 0) / Math.max(steps.length, 1))
  );

  const elapsed = (() => {
    if (startedAt === null) return null;
    if (endedAt !== null) {
      const dur = formatDuration(endedAt - startedAt);
      return failed ? `Stopped after ${dur}` : `Done in ${dur}`;
    }
    return formatDuration(now - startedAt);
  })();

  return (
    <div className="space-y-5">
      <div className="flex justify-between items-baseline">
        <h3 className="text-xs font-bold uppercase tracking-widest text-muted-foreground">Progress</h3>
        {elapsed && (
          <span
            className={cn(
              'text-xs font-semibold tabular-nums',
              failed ? 'text-destructive' : endedAt !== null ? 'text-success' : 'text-muted-foreground'
            )}
          >
            {elapsed}
          </span>
        )}
      </div>

      <Progress value={overall} className={cn('h-2.5 bg-muted', STEP_FILLS[overallStatus])} />

      <div className="space-y-4" role="list" aria-label="Processing steps">
        {steps.map(step => {
          const Icon = STEP_ICON[step.status];
          return (
            <div key={step.id} className="space-y-2" role="listitem">
              <div className="flex justify-between items-center text-sm">
                <span className={cn('font-semibold flex items-center gap-2', STEP_LABEL_COLORS[step.status])}>
                  <Icon aria-hidden="true" className={cn('size-4', step.status === 'processing' && 'animate-spin')} />
                  {step.label}
                </span>
                <span className="text-muted-foreground text-xs tabular-nums" aria-label={`${step.progress}%`}>
                  {step.progress}%
                </span>
              </div>
              <Progress value={step.progress} className={cn('h-1.5 bg-muted', STEP_FILLS[step.status])} />
            </div>
          );
        })}
      </div>
    </div>
  );
};

const Translator: React.FC<TranslatorProps> = ({
  settings,
  isProcessing,
  steps,
  logs,
  result,
  error,
  startedAt,
  liveSegment,
  onStart,
  onReset,
}) => {
  const [file, setFileState] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [config, setConfig] = useState<SubtitleConfig>(() => {
    const saved = localStorage.getItem(CONFIG_KEY);
    if (saved) {
      try { return JSON.parse(saved); } catch (e) { console.warn('Failed to parse translator config', e); }
    }
    return {
      sourceLang: 'auto', targetLang: 'en',
      enableDiarization: false, qualityVerification: true,
      burnSubtitles: true, font: 'Helvetica', fontSize: 14,
      position: 'Bottom Center', shadow: 1, outline: 1, subtitleFormat: 'srt'
    };
  });

  // Live session state (absorbed from LivePreview)
  const [lookahead, setLookahead] = useState(30);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [liveStatus, setLiveStatus] = useState<LiveStatusResponse | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [stoppedSrtToken, setStoppedSrtToken] = useState<string | null>(null);
  const [, setTick] = useState(0);
  const videoRef = useRef<HTMLVideoElement>(null);
  const pollRef = useRef<number | null>(null);
  const failCountRef = useRef(0);

  React.useEffect(() => {
    localStorage.setItem(CONFIG_KEY, JSON.stringify(config));
  }, [config]);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  // New file clears any finished live session leftovers
  useEffect(() => {
    setStoppedSrtToken(null);
    setLiveError(null);
  }, [file]);

  const setFile = (f: File | null) => setFileState(f);

  const set = <K extends keyof SubtitleConfig>(key: K, value: SubtitleConfig[K]) =>
    setConfig(prev => ({ ...prev, [key]: value }));

  /* ---------- live session ---------- */

  const clearPolling = () => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const poll = async (sid: string) => {
    const video = videoRef.current;
    const position = video ? video.currentTime : 0;
    const state = video && !video.paused && !video.ended ? 'Playing' : 'Paused';
    try {
      const status = await api.liveStatus(sid, position, state);
      setLiveStatus(status);
      failCountRef.current = 0;
      if (status.error) {
        clearPolling();
        api.liveStop(sid).catch(() => {});
        setLiveError(status.error);
        setSessionId(null);
      }
    } catch {
      failCountRef.current += 1;
      if (failCountRef.current >= 20) {
        clearPolling();
        api.liveStop(sid).catch(() => {});
        setLiveError('Lost connection to backend.');
        setSessionId(null);
      }
    }
  };

  const startLive = async () => {
    if (!file || isProcessing) return;
    setIsStarting(true);
    setLiveError(null);
    setStoppedSrtToken(null);
    try {
      const res: LiveStartResponse = await api.liveStartUpload(file, {
        source_lang: config.sourceLang,
        target_lang: config.targetLang,
        lookahead_seconds: lookahead,
        whisper_model: settings.localWhisperModel,
        llm_model: settings.localLlmModel,
        local_llm_file: settings.localLlmFile,
      });
      setSessionId(res.session_id);
      // Seed from the start response so the "preparing video" spinner is correct
      // from t=0 (first real status poll is 500ms later; until then the raw,
      // non-browser-decodable source would have been mounted by mistake).
      setLiveStatus({
        transcoding: res.transcoding,
        transcode_progress: 0,
        hls: res.hls,
        playlist_ready: false,
        segments: [],
        error: null,
      } as unknown as LiveStatusResponse);
      pollRef.current = window.setInterval(() => poll(res.session_id), 500);
    } catch (e) {
      setLiveError(e instanceof Error ? e.message : 'Failed to start live translation');
    } finally {
      setIsStarting(false);
    }
  };

  const stopLive = async () => {
    if (!sessionId) return;
    clearPolling();
    setIsStopping(true);
    let token: string | null = null;
    try {
      let r = await api.liveStop(sessionId);
      // 202: the worker has not exited yet; keep retrying until cleanup is done.
      while (r.status === 'stopping') {
        await new Promise(resolve => setTimeout(resolve, 1000));
        r = await api.liveStop(sessionId);
      }
      token = r.srt_download_token ?? null;
    } catch { /* session already gone */ }
    setStoppedSrtToken(token);
    setSessionId(null);
    setIsStopping(false);
  };

  useEffect(() => () => clearPolling(), []);

  // App records only the start time; snapshot the moment processing stops so the
  // pipeline can show "Done in" instead of ticking forever.
  const [endedAt, setEndedAt] = useState<{ startedAt: number; at: number } | null>(null);
  useEffect(() => {
    if (startedAt === null) setEndedAt(null);
    else if (!isProcessing) {
      setEndedAt(prev => (prev?.startedAt === startedAt ? prev : { startedAt, at: Date.now() }));
    }
  }, [startedAt, isProcessing]);

  /* ---------- derived ---------- */

  const liveRunning = sessionId !== null;
  const stageMode: StageMode = result
    ? 'done'
    : isProcessing
    ? 'processing'
    : liveRunning
    ? 'live'
    : file
    ? 'preview'
    : 'empty';

  const resultUrl = useMemo(
    () => (result?.downloads?.video ? `/api/download?token=${encodeURIComponent(result.downloads.video)}` : null),
    [result]
  );

  const latestLog = isProcessing && logs.length > 0 ? logs[logs.length - 1] : null;
  const hasActivity = isProcessing || startedAt !== null;
  const configVisible = !isProcessing && !result && !liveRunning;
  const pipelineEndedAt = endedAt !== null && endedAt.startedAt === startedAt ? endedAt.at : null;

  const currentPosition = liveRunning ? (videoRef.current?.currentTime ?? 0) : 0;
  const currentLiveSegment = liveRunning
    ? (liveStatus?.segments?.find(s => s.start <= currentPosition && currentPosition < s.end) ?? null)
    : null;
  const upcoming = liveRunning
    ? (liveStatus?.segments?.filter(seg => seg.start > currentPosition).sort((a, b) => a.start - b.start).slice(0, 4) ?? [])
    : [];
  const bufferHealth = liveStatus?.buffer_health_seconds ?? 0;
  const bufferFill = Math.min(100, (bufferHealth / lookahead) * 100);
  const bufferColor = bufferHealth > 15 ? 'bg-success' : bufferHealth >= 5 ? 'bg-warning' : 'bg-destructive';
  // The token is registered at session start but the file only exists after the
  // first write (the route 404s until then), so gate the link on real subtitles.
  const srtToken = (liveStatus?.segments?.length ? liveStatus.srt_download_token : null) ?? stoppedSrtToken;
  const displayLiveError = liveError || liveStatus?.error || null;
  const friendlyLiveError = displayLiveError ? describeError(displayLiveError) : null;

  const overlaySegment = liveRunning && currentLiveSegment
    ? { original: currentLiveSegment.original, text: currentLiveSegment.text, speaker: currentLiveSegment.speaker }
    : liveSegment;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[230px_minmax(0,1fr)_280px] gap-5 items-start">
      {/* Visually hidden live region for screen reader announcements */}
      <div aria-live="polite" aria-atomic="true" className="sr-only">
        {steps.find(s => s.status === 'processing')?.label
          ? `Processing: ${steps.find(s => s.status === 'processing')!.label}`
          : result
          ? 'Translation complete. Files are ready to download.'
          : liveRunning
          ? 'Live translation running.'
          : ''}
      </div>

      {/* LEFT RAIL — pipeline / live status */}
      <aside className="space-y-5 order-2 lg:order-1 lg:sticky lg:top-20">
        {liveRunning ? (
          <Card title="Live session">
            <div className="space-y-3">
              <div className="flex justify-between text-xs font-semibold text-muted-foreground">
                <span>Buffer</span>
                <span className="tabular-nums">{bufferHealth.toFixed(0)}s ahead</span>
              </div>
              <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                <div className={`h-full rounded-full transition-all ${bufferColor}`} style={{ width: `${bufferFill}%` }} />
              </div>
              <p className="text-xs text-muted-foreground">
                {liveStatus ? `${liveStatus.segments.length} subtitles generated` : 'Waiting for status…'}
              </p>
            </div>
          </Card>
        ) : hasActivity ? (
          <Card>
            <Pipeline steps={steps} startedAt={startedAt} endedAt={pipelineEndedAt} failed={!!error && !isProcessing} />
          </Card>
        ) : null}
        <Card title="Engine">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-muted-foreground">Transcription</dt>
              <dd className="font-semibold text-foreground truncate">{settings.localWhisperModel}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-muted-foreground">Translation</dt>
              <dd className="font-semibold text-foreground truncate font-mono text-xs pt-0.5">{settings.localLlmFile}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-muted-foreground">GPU encoding</dt>
              <dd className={`font-semibold ${settings.useGpuEncoding ? 'text-success' : 'text-muted-foreground'}`}>
                {settings.useGpuEncoding ? 'On' : 'Off'}
              </dd>
            </div>
          </dl>
          <p className="text-xs text-muted-foreground mt-4">
            Change models in <span className="font-semibold text-foreground">Settings</span>.
          </p>
        </Card>
        {(hasActivity || liveRunning) && (
          <LogsConsole logs={liveRunning ? (liveStatus?.logs ?? []) : logs} ariaLabel="Translation logs" />
        )}
      </aside>

      {/* CENTER — stage */}
      <main className="space-y-5 order-1 lg:order-2 min-w-0">
        {stageMode === 'empty' && (
          <div className="enter-slide-up">
            <h2 className="text-xl font-bold text-foreground">Studio-grade subtitles in minutes.</h2>
            <p className="text-sm text-muted-foreground mt-1">Drop a video and go — everything runs locally on your machine.</p>
          </div>
        )}

        <StageCanvas
          mode={stageMode}
          file={file}
          previewUrl={previewUrl}
          resultUrl={resultUrl}
          steps={steps}
          latestLog={latestLog}
          liveSegment={overlaySegment}
          sessionId={sessionId}
          liveStatus={liveStatus}
          videoRef={videoRef}
          onLiveTimeUpdate={() => setTick(t => t + 1)}
          onLiveError={() => setLiveError('Video playback error')}
          onLiveRecover={() => setLiveError(null)}
          onFile={setFile}
          onRemove={() => {
            stopLive();
            setFile(null);
          }}
        />

        {liveRunning && liveStatus?.models_loading && (
          <div className="flex items-center gap-3 p-3 rounded-lg bg-accent border border-border">
            <span className="h-4 w-4 rounded-full border-2 border-brand border-t-transparent animate-spin shrink-0" aria-hidden="true" />
            <p className="text-sm font-medium text-foreground">
              Loading AI models — press play now, first subtitles will appear once ready…
            </p>
          </div>
        )}
        {liveRunning && liveStatus?.remuxed && (
          <p className="text-xs text-muted-foreground">Video was remuxed to MP4 for browser playback (no quality loss).</p>
        )}

        {upcoming.length > 0 && (
          <Card title="Upcoming subtitles">
            <ul className="space-y-2">
              {upcoming.map((seg, i) => (
                <li key={i} className="flex items-baseline gap-2 text-sm text-muted-foreground">
                  <span className="font-mono text-xs shrink-0 text-muted-foreground tabular-nums">[{formatTime(seg.start)}]</span>
                  <span className="truncate">{seg.text}</span>
                </li>
              ))}
            </ul>
          </Card>
        )}

        {configVisible && (
          <div className="space-y-4 enter-slide-up">
            <div className="grid grid-cols-1 sm:grid-cols-[1fr_auto_1fr] gap-3 items-end">
              <div>
                <FormLabel htmlFor="source-lang">From</FormLabel>
                <Select value={config.sourceLang} onValueChange={(v) => set('sourceLang', v)}>
                  <SelectTrigger id="source-lang" className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SOURCE_LANGUAGES.map(l => <SelectItem key={l.value} value={l.value}>{l.label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="hidden sm:flex pb-3 text-muted-foreground justify-center" aria-hidden="true">
                <ArrowRight className="size-5" />
              </div>
              <div>
                <FormLabel>Into</FormLabel>
                <div
                  className="w-full bg-card border border-border rounded-lg px-4 py-3 text-foreground select-none"
                  aria-label="Target language"
                >
                  English
                </div>
              </div>
            </div>

            <OptionsDrawer config={config} onChange={set} />

            <div>
              <FormLabel>Live preview lookahead</FormLabel>
              <div className="flex gap-2" role="group" aria-label="Lookahead window">
                {LOOKAHEAD_PRESETS.map(p => (
                  <button
                    key={p.value}
                    onClick={() => setLookahead(p.value)}
                    aria-pressed={lookahead === p.value}
                    className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold border transition-all focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 ${
                      lookahead === p.value
                        ? 'bg-brand/10 border-brand/40 text-brand shadow-sm'
                        : 'bg-card border-border text-muted-foreground hover:border-brand/40'
                    }`}
                  >
                    {p.label.split(' ')[0]}
                  </button>
                ))}
              </div>
            </div>

            {error && (
              <Banner variant="error">
                <div className="flex items-center justify-between gap-4">
                  <span>{error}</span>
                  {file && (
                    <Button size="sm" variant="outline" onClick={() => onStart(file, config)}>
                      Retry
                    </Button>
                  )}
                </div>
              </Banner>
            )}
          </div>
        )}

        {displayLiveError && (
          <Banner variant="error">
            {friendlyLiveError !== displayLiveError ? (
              <>
                <p>{friendlyLiveError}</p>
                <p className="mt-1 font-mono text-xs opacity-80">{displayLiveError}</p>
              </>
            ) : (
              <p>{displayLiveError}</p>
            )}
          </Banner>
        )}

      </main>

      {/* RIGHT RAIL — output + one primary action */}
      <aside className="space-y-5 order-3 lg:sticky lg:top-20">
        {result ? (
          <Card>
            <ResultsPanel result={result} onReset={onReset} />
          </Card>
        ) : liveRunning || stoppedSrtToken ? (
          <>
            <Card title="Output">
              {srtToken ? (
                <div className="flex items-center justify-between gap-3 rounded-lg border p-3">
                  <div className="min-w-0">
                    <p className="font-semibold text-foreground truncate text-sm">Live subtitles</p>
                    <p className="text-xs text-muted-foreground">SRT file, updates while the session runs</p>
                  </div>
                  <Button asChild size="sm" variant="outline">
                    <a href={`/api/download?token=${encodeURIComponent(srtToken)}`} download>
                      <Download />
                      Download
                    </a>
                  </Button>
                </div>
              ) : (
                <p className="text-xs text-muted-foreground leading-relaxed">SRT file will appear here once subtitles are generated.</p>
              )}
            </Card>
            {liveRunning ? (
              <Button
                variant="outline"
                size="lg"
                className="h-12 w-full text-base border-destructive/40 text-destructive hover:bg-destructive/10 hover:text-destructive"
                onClick={stopLive}
                disabled={isStopping}
              >
                {isStopping ? 'Stopping…' : 'Stop'}
              </Button>
            ) : (
              file && (
                <>
                  <Button
                    size="lg"
                    className="h-12 w-full text-base bg-action text-action-foreground hover:bg-action-hover"
                    onClick={startLive}
                    disabled={isStarting || isProcessing}
                  >
                    {isStarting ? 'Starting…' : 'Watch live again'}
                  </Button>
                  {isProcessing && (
                    <p className="text-xs text-muted-foreground text-center">
                      Full-video translation is running — one GPU job at a time.
                    </p>
                  )}
                </>
              )
            )}
            {liveRunning && (
              <>
                <Button variant="link" size="sm" className="w-full" disabled>
                  or translate the full video →
                </Button>
                <p className="text-xs text-muted-foreground text-center">
                  Stop the live session first — one GPU job at a time.
                </p>
              </>
            )}
          </>
        ) : (
          <>
            <Card title="Output">
              {!file ? (
                <p className="text-xs text-muted-foreground leading-relaxed">
                  Your files will land here — subtitle file{config.burnSubtitles ? ' and burned video' : ''}.
                </p>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3 rounded-lg border p-3 opacity-70">
                    <div className="min-w-0">
                      <p className="font-semibold text-foreground truncate text-sm">{file.name.replace(/\.[^.]+$/, '')}.{config.subtitleFormat}</p>
                      <p className="text-xs text-muted-foreground">Subtitle file</p>
                    </div>
                    <Badge variant="secondary">
                      {isProcessing ? 'queued' : 'waiting'}
                    </Badge>
                  </div>
                  {config.burnSubtitles && (
                    <div className="flex items-center justify-between gap-3 rounded-lg border p-3 opacity-70">
                      <div className="min-w-0">
                        <p className="font-semibold text-foreground truncate text-sm">{file.name.replace(/\.[^.]+$/, '')}{settings.outputSuffix || '_translated'}.mp4</p>
                        <p className="text-xs text-muted-foreground">Burned video</p>
                      </div>
                      <Badge variant="secondary">
                        {isProcessing ? 'queued' : 'waiting'}
                      </Badge>
                    </div>
                  )}
                </div>
              )}
            </Card>

            <Button
              size="lg"
              className="h-12 w-full text-base bg-action text-action-foreground hover:bg-action-hover"
              onClick={startLive}
              disabled={!file || isStarting || isProcessing}
            >
              {isStarting ? 'Starting…' : 'Watch with live subtitles'}
            </Button>
            {isProcessing && (
              <p className="text-xs text-muted-foreground text-center">
                Full-video translation is running — one GPU job at a time.
              </p>
            )}
            {file && !isProcessing && !isStarting && (
              <>
                <Button
                  variant="link"
                  size="sm"
                  className="w-full"
                  onClick={() => onStart(file, config)}
                >
                  or translate the full video →
                </Button>
                <p className="text-xs text-muted-foreground text-center">
                  Everything is local — nothing leaves your machine.
                </p>
              </>
            )}
          </>
        )}
      </aside>
    </div>
  );
};

export default Translator;

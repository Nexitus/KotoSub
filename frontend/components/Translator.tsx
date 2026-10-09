import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AppSettings, SubtitleConfig, ProcessingStep, LiveStartResponse, LiveStatusResponse } from '../types';
import { SOURCE_LANGUAGES, LOOKAHEAD_PRESETS, ICONS } from '../constants';
import { api } from '../services/api';
import StageCanvas, { StageMode } from './StageCanvas';
import StepRail from './StepRail';
import OptionsDrawer from './OptionsDrawer';
import ResultsPanel from './ResultsPanel';
import LogsConsole from './LogsConsole';
import Card from './Card';
import Banner from './ui/Banner';
import FormLabel from './ui/FormLabel';
import Select from './ui/Select';

interface TranslatorProps {
  settings: AppSettings;
  isProcessing: boolean;
  steps: ProcessingStep[];
  logs: string[];
  result: any;
  error: string | null;
  startedAt: number | null;
  finishedAt: number | null;
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
  if (lower.includes('file not found')) return 'Video file not found. Check the path and try again.';
  if (lower.includes('ffmpeg')) return 'FFmpeg is required but could not run. Check the backend installation.';
  if (lower.includes('codec')) return 'The video codec is not supported for in-browser playback.';
  if (lower.includes('permission denied') || lower.includes('access denied')) return 'Access to the video file was denied.';
  return raw;
};

const Translator: React.FC<TranslatorProps> = ({
  settings,
  isProcessing,
  steps,
  logs,
  result,
  error,
  startedAt,
  finishedAt,
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
  const [liveError, setLiveError] = useState<string | null>(null);
  const [stoppedSrt, setStoppedSrt] = useState<string | null>(null);
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
    setStoppedSrt(null);
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
    if (!file) return;
    setIsStarting(true);
    setLiveError(null);
    setStoppedSrt(null);
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
    try {
      const r = await api.liveStop(sessionId);
      setStoppedSrt(r.srt_file_path);
    } catch { /* session already gone */ }
    setSessionId(null);
  };

  useEffect(() => () => clearPolling(), []);

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
    () => (result?.video_output ? `/api/download?path=${encodeURIComponent(result.video_output)}` : null),
    [result]
  );

  const latestLog = isProcessing && logs.length > 0 ? logs[logs.length - 1] : null;
  const hasActivity = isProcessing || startedAt !== null;
  const configVisible = !isProcessing && !result && !liveRunning;

  const currentPosition = liveRunning ? (videoRef.current?.currentTime ?? 0) : 0;
  const currentLiveSegment = liveRunning
    ? (liveStatus?.segments?.find(s => s.start <= currentPosition && currentPosition < s.end) ?? null)
    : null;
  const upcoming = liveRunning
    ? (liveStatus?.segments?.filter(seg => seg.start > currentPosition).sort((a, b) => a.start - b.start).slice(0, 4) ?? [])
    : [];
  const bufferHealth = liveStatus?.buffer_health_seconds ?? 0;
  const bufferFill = Math.min(100, (bufferHealth / lookahead) * 100);
  const bufferColor = bufferHealth > 15 ? 'bg-success' : bufferHealth >= 5 ? 'bg-warning' : 'bg-error';
  const srtPath = liveStatus?.srt_file_path ?? stoppedSrt;
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
              <div className="flex justify-between text-xs font-semibold text-ink-soft">
                <span>Buffer</span>
                <span className="tabular-nums">{bufferHealth.toFixed(0)}s ahead</span>
              </div>
              <div className="w-full h-2 bg-edge/60 rounded-full overflow-hidden">
                <div className={`h-full rounded-full transition-all ${bufferColor}`} style={{ width: `${bufferFill}%` }} />
              </div>
              <p className="text-xs text-ink-faint">
                {liveStatus ? `${liveStatus.segments.length} subtitles generated` : 'Waiting for status…'}
              </p>
            </div>
          </Card>
        ) : hasActivity ? (
          <Card>
            <StepRail steps={steps} startedAt={startedAt} finishedAt={finishedAt} failed={!!error && !isProcessing} />
          </Card>
        ) : null}
        <Card title="Engine">
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-ink-faint">Transcription</dt>
              <dd className="font-semibold text-ink truncate">{settings.localWhisperModel}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-ink-faint">Translation</dt>
              <dd className="font-semibold text-ink truncate font-mono text-xs pt-0.5">{settings.localLlmFile}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-ink-faint">GPU encoding</dt>
              <dd className={`font-semibold ${settings.useGpuEncoding ? 'text-success' : 'text-ink-faint'}`}>
                {settings.useGpuEncoding ? 'On' : 'Off'}
              </dd>
            </div>
          </dl>
          <p className="text-xs text-ink-faint mt-4">
            Change models in <span className="font-semibold text-ink-soft">Settings</span>.
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
            <h2 className="text-xl font-bold text-ink">Studio-grade subtitles in minutes.</h2>
            <p className="text-sm text-ink-soft mt-1">Drop a video and go — everything runs locally on your machine.</p>
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
          <div className="flex items-center gap-3 p-3 rounded-lg bg-brand-soft border border-brand/20">
            <span className="h-4 w-4 rounded-full border-2 border-brand border-t-transparent animate-spin shrink-0" aria-hidden="true" />
            <p className="text-sm font-medium text-brand">
              Loading AI models — press play now, first subtitles will appear once ready…
            </p>
          </div>
        )}
        {liveRunning && liveStatus?.remuxed && (
          <p className="text-xs text-ink-faint">Video was remuxed to MP4 for browser playback (no quality loss).</p>
        )}

        {upcoming.length > 0 && (
          <Card title="Upcoming subtitles">
            <ul className="space-y-2">
              {upcoming.map((seg, i) => (
                <li key={i} className="flex items-baseline gap-2 text-sm text-ink-soft">
                  <span className="font-mono text-xs shrink-0 text-ink-faint tabular-nums">[{formatTime(seg.start)}]</span>
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
                <Select id="source-lang" value={config.sourceLang} onChange={(e) => set('sourceLang', e.target.value)}>
                  {SOURCE_LANGUAGES.map(l => <option key={l.value + l.label} value={l.value}>{l.label}</option>)}
                </Select>
              </div>
              <div className="hidden sm:flex pb-3 text-ink-faint justify-center" aria-hidden="true">
                <ICONS.ArrowRight />
              </div>
              <div>
                <FormLabel>Into</FormLabel>
                <div
                  className="w-full bg-raised border border-edge rounded-lg px-4 py-3 text-ink select-none"
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
                    className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold border transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 ${
                      lookahead === p.value
                        ? 'bg-brand-soft border-brand/40 text-brand shadow-sm'
                        : 'bg-raised border-edge text-ink-faint hover:border-brand/40'
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
                    <button
                      onClick={() => onStart(file, config)}
                      className="shrink-0 text-xs font-bold underline hover:no-underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-current rounded"
                    >
                      Retry
                    </button>
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
        ) : liveRunning || stoppedSrt ? (
          <>
            <Card title="Output">
              {srtPath ? (
                <div className="flex items-center justify-between gap-3 p-3 bg-raised border border-edge rounded-xl">
                  <div className="min-w-0">
                    <p className="font-semibold text-ink truncate text-sm">{srtPath.split(/[/\\]/).pop()}</p>
                    <p className="text-xs text-ink-faint">Live subtitles (SRT)</p>
                  </div>
                  <a
                    href={`/api/download?path=${encodeURIComponent(srtPath)}`}
                    className="shrink-0 inline-flex items-center gap-1.5 text-sm font-bold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 rounded"
                    download
                  >
                    <ICONS.Download />
                    Download
                  </a>
                </div>
              ) : (
                <p className="text-xs text-ink-faint leading-relaxed">SRT file will appear here once subtitles are generated.</p>
              )}
            </Card>
            {liveRunning ? (
              <button
                onClick={stopLive}
                className="w-full py-4 rounded-xl bg-transparent text-error border-2 border-error/40 font-bold text-lg transition-all hover:bg-error/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-error focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface)]"
              >
                Stop
              </button>
            ) : (
              file && (
                <button
                  onClick={startLive}
                  disabled={isStarting}
                  className="w-full py-4 rounded-xl bg-action hover:bg-action-hover text-white font-bold text-lg shadow-lg transition-all active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface)]"
                >
                  {isStarting ? 'Starting…' : 'Watch live again'}
                </button>
              )
            )}
          </>
        ) : (
          <>
            <Card title="Output">
              {!file ? (
                <p className="text-xs text-ink-faint leading-relaxed">
                  Your files will land here — subtitle file{config.burnSubtitles ? ' and burned video' : ''}.
                </p>
              ) : (
                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3 p-3 bg-raised border border-edge rounded-xl opacity-70">
                    <div className="min-w-0">
                      <p className="font-semibold text-ink truncate text-sm">{file.name.replace(/\.[^.]+$/, '')}.{config.subtitleFormat}</p>
                      <p className="text-xs text-ink-faint">Subtitle file</p>
                    </div>
                    <span className="shrink-0 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-edge/70 text-ink-faint">
                      {isProcessing ? 'queued' : 'waiting'}
                    </span>
                  </div>
                  {config.burnSubtitles && (
                    <div className="flex items-center justify-between gap-3 p-3 bg-raised border border-edge rounded-xl opacity-70">
                      <div className="min-w-0">
                        <p className="font-semibold text-ink truncate text-sm">{file.name.replace(/\.[^.]+$/, '')}{settings.outputSuffix || '_translated'}.mp4</p>
                        <p className="text-xs text-ink-faint">Burned video</p>
                      </div>
                      <span className="shrink-0 text-[11px] font-semibold px-2 py-0.5 rounded-full bg-edge/70 text-ink-faint">
                        {isProcessing ? 'queued' : 'waiting'}
                      </span>
                    </div>
                  )}
                </div>
              )}
            </Card>

            <button
              onClick={startLive}
              disabled={!file || isStarting}
              className="w-full py-4 rounded-xl bg-action hover:bg-action-hover text-white font-bold text-lg shadow-lg transition-all active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-action focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-action focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface)]"
            >
              {isStarting ? 'Starting…' : 'Watch with live subtitles'}
            </button>
            {file && !isProcessing && (
              <>
                <button
                  onClick={() => onStart(file, config)}
                  className="w-full text-xs font-semibold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 rounded py-1"
                >
                  or translate the full video →
                </button>
                <p className="text-xs text-ink-faint text-center">
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

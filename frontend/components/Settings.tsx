import React from 'react';
import { AppSettings } from '../types';
import Card from './Card';
import FormLabel from './ui/FormLabel';
import Input from './ui/Input';
import Select from './ui/Select';
import CheckboxField from './ui/CheckboxField';
import Banner from './ui/Banner';
import { api } from '../services/api';

interface SettingsProps {
  settings: AppSettings;
  onSave: (settings: AppSettings) => void;
}

const Settings: React.FC<SettingsProps> = ({ settings, onSave }) => {
  const [llmModels, setLlmModels] = React.useState<Array<{ label: string; repo: string; file: string; installed: boolean }>>([]);
  const [whisperModels, setWhisperModels] = React.useState<{ label: string; value: string; installed: boolean }[]>([]);
  const [gpuInfo, setGpuInfo] = React.useState<{ available: boolean; name: string | null; vram_total_mb: number | null; detected_gpu: boolean } | null>(null);
  const [downloadKind, setDownloadKind] = React.useState<string | null>(null);
  const [downloadLogs, setDownloadLogs] = React.useState<string[]>([]);
  const [downloadError, setDownloadError] = React.useState<string | null>(null);

  const loadModels = React.useCallback(() => {
    api.getModels().then(data => {
      setLlmModels(data.llm_models);
      setWhisperModels(data.whisper_models);
    }).catch(err => console.error('Failed to load models', err));
  }, []);

  React.useEffect(() => {
    loadModels();
    api.getGpuInfo().then(setGpuInfo).catch(() => {});
  }, [loadModels]);

  const startDownload = async (kind: 'all' | 'llm' | 'whisper' | 'qwen') => {
    if (downloadKind) return;
    setDownloadError(null);
    setDownloadLogs([`Starting download for ${kind} models…`]);
    try {
      await api.downloadModels(kind);
      setDownloadKind(kind);
    } catch (e) {
      setDownloadLogs([]);
      setDownloadError(e instanceof Error ? e.message : 'Unknown error');
    }
  };

  // Poll download progress while a batch is running; refresh model status
  // (and the "(Missing)" markers) as soon as the batch finishes.
  React.useEffect(() => {
    if (!downloadKind) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const s = await api.modelDownloadStatus();
        if (cancelled) return;
        if (s.logs.length) setDownloadLogs(s.logs);
        if (s.error) setDownloadError(s.error);
        if (!s.active) {
          setDownloadKind(null);
          loadModels();
        }
      } catch {
        // transient network error — keep polling
      }
    };
    const t = window.setInterval(poll, 2000);
    return () => { cancelled = true; window.clearInterval(t); };
  }, [downloadKind, loadModels]);

  const missingCount =
    llmModels.filter(m => !m.installed).length +
    whisperModels.filter(m => !m.installed).length;
  const downloadBtn = (kind: string, label: string, primary = false) => (
    <button
      key={kind}
      onClick={() => startDownload(kind as 'all' | 'llm' | 'whisper' | 'qwen')}
      disabled={downloadKind !== null}
      className={`px-3 py-1.5 text-xs font-bold rounded-lg transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:opacity-50 disabled:cursor-not-allowed ${
        primary
          ? 'bg-brand text-white hover:brightness-110'
          : 'bg-brand-soft text-brand hover:brightness-95'
      }`}
    >
      {label}
    </button>
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    onSave({ ...settings, [e.target.name]: e.target.value });
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="mb-2">
        <h2 className="text-2xl font-bold text-ink mb-1">
          App Configuration
        </h2>
        <p className="text-sm text-ink-soft">
          Configure your AI models and output preferences.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card title="API Tokens">
          <div>
            <FormLabel htmlFor="hfToken">Hugging Face Token</FormLabel>
            <Input
              id="hfToken"
              type="password"
              name="huggingFaceToken"
              value={settings.huggingFaceToken}
              onChange={handleChange}
              placeholder="hf_..."
            />
            <p className="mt-2 text-xs text-ink-faint">Needed to label speakers in your video</p>
          </div>
        </Card>
      </div>

      <Card title="Local AI Models">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div>
            <FormLabel htmlFor="localWhisper">Transcription Model</FormLabel>
            <Select id="localWhisper" name="localWhisperModel" value={settings.localWhisperModel} onChange={handleChange}>
              {whisperModels.length > 0 ? (
                whisperModels.map(m => (
                  <option key={m.value} value={m.value}>
                    {m.label} {m.installed ? '(Installed)' : '(Missing)'}
                  </option>
                ))
              ) : (
                <>
                  <option value="medium">Medium (Balanced)</option>
                  <option value="large-v3">Large V3 (High Quality)</option>
                  <option value="large-v3-turbo">Large V3 Turbo (Best)</option>
                  <option value="distil-whisper/distil-large-v3.5-ct2">Distil Large V3.5 (Fastest)</option>
                </>
              )}
            </Select>
          </div>

          <div>
            <FormLabel htmlFor="localLlm">Translation Model</FormLabel>
            <Select
              id="localLlm"
              name="localLlmModel"
              value={settings.localLlmModel}
              className="font-medium"
              onChange={(e) => {
                const selected = llmModels.find(m => m.repo === e.target.value);
                if (selected) onSave({ ...settings, localLlmModel: selected.repo, localLlmFile: selected.file });
              }}
            >
              {llmModels.map(m => (
                <option key={m.repo} value={m.repo}>
                  {m.label} {m.installed ? '(Installed)' : '(Missing)'}
                </option>
              ))}
            </Select>
            <p className="mt-2 text-xs text-ink-faint">
              File: <span className="font-mono text-brand font-bold">{settings.localLlmFile}</span>
            </p>
          </div>

          <div className="md:col-span-2 grid grid-cols-1 md:grid-cols-2 gap-8">
            <div>
              <FormLabel htmlFor="whisperPrompt">Vocabulary Hint</FormLabel>
              <Input
                id="whisperPrompt"
                type="text"
                name="whisperPrompt"
                value={settings.whisperPrompt}
                onChange={handleChange}
                placeholder="e.g. channel name, game or series title"
              />
              <p className="mt-2 text-xs text-ink-faint">
                Steers transcription toward niche terms, names, and jargon.
              </p>
            </div>
            <div>
              <FormLabel htmlFor="whisperHotwords">Hotwords</FormLabel>
              <Input
                id="whisperHotwords"
                type="text"
                name="whisperHotwords"
                value={settings.whisperHotwords}
                onChange={handleChange}
                placeholder="e.g. Xenoblade, KotoSub, NVENC"
              />
              <p className="mt-2 text-xs text-ink-faint">
                Comma-separated words boosted during transcription.
              </p>
            </div>
          </div>

          <div className="md:col-span-2">
            <CheckboxField
              id="gpu-encoding"
              checked={settings.useGpuEncoding}
              onChange={(v) => onSave({ ...settings, useGpuEncoding: v })}
              label="AV1 / HEVC GPU Encoding"
              description={gpuInfo?.detected_gpu
                ? `Uses ${gpuInfo.name} (${gpuInfo.vram_total_mb} MB VRAM) — AV1 on RTX 40/50 series, falls back to HEVC/H.264 on older GPUs`
                : "Uses NVIDIA NVENC for faster video encoding. Requires an NVIDIA GPU."
              }
            />
            {gpuInfo?.detected_gpu && (
              <div className="mt-2 ml-8 p-2 bg-success/10 border border-success/30 rounded-lg">
                <p className="text-xs text-success">
                  GPU detected: {gpuInfo.name} · {gpuInfo.vram_total_mb} MB VRAM
                </p>
                <p className="text-xs text-success/80 mt-0.5">
                  Codec chain: AV1 (RTX 40/50+) → HEVC → H.264 → CPU fallback
                </p>
              </div>
            )}
          </div>
        </div>
      </Card>

      <Card title="Model Downloads">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-ink-soft mr-1">
              {missingCount === 0
                ? 'All models are installed.'
                : `${missingCount} model${missingCount === 1 ? '' : 's'} missing.`}
            </span>
            {downloadBtn('all', 'Download All Missing', true)}
            {downloadBtn('llm', 'Translation (LLM)')}
            {downloadBtn('whisper', 'Transcription (Whisper)')}
            {downloadBtn('qwen', 'Qwen3-ASR')}
            {downloadKind && (
              <span className="text-xs text-ink-soft animate-pulse ml-1">
                Downloading {downloadKind} models… (multi-GB, this takes a while)
              </span>
            )}
          </div>

          {downloadError && (
            <Banner variant="warning">{downloadError}</Banner>
          )}

          {downloadLogs.length > 0 && (
            <div className="max-h-40 overflow-y-auto rounded-lg bg-raised border border-edge p-3">
              {downloadLogs.map((line, i) => (
                <pre key={i} className="font-mono text-xs text-ink-soft whitespace-pre-wrap break-words">
                  {line}
                </pre>
              ))}
            </div>
          )}

          <p className="text-xs text-ink-faint">
            Only missing models are downloaded. Qwen3-ASR additionally needs the
            optional <span className="font-mono">qwen-asr</span> package on the server
            (<span className="font-mono">pip install qwen-asr</span>).
          </p>
        </div>
      </Card>

      <Card title="Export & Naming">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div>
            <FormLabel htmlFor="outputSuffix">Filename Suffix</FormLabel>
            <Input
              id="outputSuffix"
              type="text"
              name="outputSuffix"
              value={settings.outputSuffix}
              onChange={handleChange}
              placeholder="_translated"
              className="font-mono"
            />
            <p className="mt-2 text-xs text-ink-faint">
              Example: original{settings.outputSuffix}.srt
            </p>
          </div>
          <div className="flex items-center">
            <CheckboxField
              id="include-lang"
              checked={settings.includeLanguageInName}
              onChange={(v) => onSave({ ...settings, includeLanguageInName: v })}
              label="Include Language Code"
              description="Append _en to the filename."
            />
          </div>
        </div>
      </Card>

      <Card title="Advanced">
        <div className="grid grid-cols-1 gap-6">
          <div>
            <FormLabel htmlFor="outputDir">Output Directory</FormLabel>
            <Input id="outputDir" type="text" name="outputDir" value={settings.outputDir} onChange={handleChange} />
            <p className="mt-2 text-xs text-ink-faint">Changes save automatically.</p>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default Settings;

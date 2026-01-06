
import React, { useState, useCallback } from 'react';
import { AppSettings, SubtitleConfig, ProcessingStep } from '../types';
import { SOURCE_LANGUAGES, TARGET_LANGUAGES, SUBTITLE_FORMATS, FONTS, POSITIONS, COLORS, ICONS } from '../constants';
import ProgressBar from './ProgressBar';
import Card from './Card';
import { api } from '../services/api';

interface TranslatorProps {
  settings: AppSettings;
  isProcessing: boolean;
  steps: ProcessingStep[];
  logs: string[];
  result: any;
  error: string | null;
  onStart: (file: File, config: SubtitleConfig) => void;
}

const Translator: React.FC<TranslatorProps> = ({
  settings,
  isProcessing,
  steps,
  logs,
  result,
  error,
  onStart
}) => {
  const CONFIG_KEY = 'kotosub_translator_config_v1';

  const [file, setFile] = useState<File | null>(null);
  const [config, setConfig] = useState<SubtitleConfig>(() => {
    const saved = localStorage.getItem(CONFIG_KEY);
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        console.warn('Failed to parse translator config from localStorage', e);
      }
    }
    return {
      sourceLang: 'auto',
      targetLang: 'en',
      enableDiarization: false,
      qualityVerification: true,
      burnSubtitles: true,
      font: 'Helvetica',
      fontSize: 14,
      position: 'Bottom Center',
      shadow: 1,
      outline: 1,
      subtitleFormat: 'srt'
    };
  });

  // Save config to localStorage whenever it changes
  React.useEffect(() => {
    localStorage.setItem(CONFIG_KEY, JSON.stringify(config));
  }, [config]);

  // Auto-scroll state for logs
  const [autoScrollLogs, setAutoScrollLogs] = useState(true);
  const logsContainerRef = React.useRef<HTMLDivElement>(null);

  // Auto-scroll effect when logs update
  React.useEffect(() => {
    if (autoScrollLogs && logsContainerRef.current) {
      logsContainerRef.current.scrollTop = logsContainerRef.current.scrollHeight;
    }
  }, [logs, autoScrollLogs]);

  // Handle manual scroll - pause auto-scroll if user scrolls up
  const handleLogsScroll = () => {
    if (logsContainerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = logsContainerRef.current;
      const isAtBottom = Math.abs(scrollHeight - scrollTop - clientHeight) < 10;

      if (!isAtBottom && autoScrollLogs) {
        setAutoScrollLogs(false);
      } else if (isAtBottom && !autoScrollLogs) {
        setAutoScrollLogs(true);
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleStart = () => {
    if (file) {
      onStart(file, config);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
      {/* Left Column: Config */}
      <div className="lg:col-span-7 space-y-6">
        <Card title="1. Upload Video">
          <div
            className={`border-2 border-dashed rounded-xl p-8 transition-all flex flex-col items-center justify-center space-y-4 cursor-pointer hover:bg-gray-50 ${file ? 'border-telus-green bg-green-50' : 'border-gray-200'
              }`}
            onClick={() => document.getElementById('video-upload')?.click()}
          >
            <input
              type="file"
              id="video-upload"
              className="hidden"
              accept="video/*"
              onChange={handleFileChange}
            />
            <div className={`p-3 rounded-full ${file ? 'bg-telus-green text-white' : 'bg-gray-100 text-gray-400'}`}>
              <ICONS.Video />
            </div>
            <div className="text-center">
              <p className="font-semibold text-gray-700">
                {file ? file.name : 'Drop video files here or click to browse'}
              </p>
              <p className="text-sm text-gray-500">
                {file ? `${(file.size / (1024 * 1024)).toFixed(1)} MB` : 'MP4, MOV, MKV up to 2GB'}
              </p>
            </div>
            {file && (
              <button
                className="text-sm font-medium text-red-500 hover:text-red-700 mt-2"
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                }}
              >
                Remove File
              </button>
            )}
          </div>
        </Card>

        <Card title="2. Language Selection">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Source Language</label>
              <select
                className="w-full bg-white border border-gray-200 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                value={config.sourceLang}
                onChange={(e) => setConfig({ ...config, sourceLang: e.target.value })}
              >
                {SOURCE_LANGUAGES.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Target Language</label>
              <select
                className="w-full bg-white border border-gray-200 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                value={config.targetLang}
                onChange={(e) => setConfig({ ...config, targetLang: e.target.value })}
              >
                {TARGET_LANGUAGES.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
              </select>
            </div>
          </div>
        </Card>

        <Card title="3. Processing Options">
          <div className="space-y-4">
            <label className="flex items-center space-x-3 cursor-pointer group">
              <input
                type="checkbox"
                className="w-5 h-5 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                checked={config.enableDiarization}
                onChange={(e) => setConfig({ ...config, enableDiarization: e.target.checked })}
              />
              <div className="flex flex-col">
                <span className="font-medium text-gray-700">Enable Speaker Diarization</span>
                <span className="text-xs text-gray-400 italic">Requires Hugging Face Token in Settings</span>
              </div>
            </label>
            <label className="flex items-center space-x-3 cursor-pointer group">
              <input
                type="checkbox"
                className="w-5 h-5 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                checked={config.qualityVerification}
                onChange={(e) => setConfig({ ...config, qualityVerification: e.target.checked })}
              />
              <div className="flex flex-col">
                <span className="font-medium text-gray-700">AI Quality Verification</span>
                <span className="text-xs text-gray-400 italic">Extra pass for accuracy</span>
              </div>
            </label>
          </div>
        </Card>

        <Card title="4. Output Format">
          <div className="space-y-6">
            <label className="flex items-center space-x-3 cursor-pointer">
              <input
                type="checkbox"
                className="w-5 h-5 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                checked={config.burnSubtitles}
                onChange={(e) => setConfig({ ...config, burnSubtitles: e.target.checked })}
              />
              <div className="flex flex-col">
                <span className="font-medium text-gray-700">Burn Subtitles into Video</span>
                <span className="text-xs text-gray-400 italic">Re-encodes video (Slower)</span>
              </div>
            </label>

            <div className="space-y-2">
              <label className="block text-xs font-bold uppercase tracking-wider text-gray-400">Subtitle Format</label>
              <div className="flex gap-2">
                {SUBTITLE_FORMATS.map(f => (
                  <button
                    key={f.value}
                    onClick={() => setConfig({ ...config, subtitleFormat: f.value as any })}
                    className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold border transition-all ${config.subtitleFormat === f.value
                      ? 'bg-purple-50 border-purple-200 text-purple-700 shadow-sm'
                      : 'bg-white border-gray-200 text-gray-400 hover:border-purple-100'
                      }`}
                  >
                    {f.label.split(' ')[0]}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bg-gray-50 rounded-xl border border-gray-100">
              <div>
                <label className="block text-xs font-bold uppercase text-gray-400 mb-1">Font</label>
                <select
                  className="w-full bg-white border border-gray-200 rounded-lg px-2 py-2 text-sm focus:outline-none"
                  value={config.font}
                  onChange={(e) => setConfig({ ...config, font: e.target.value })}
                >
                  {FONTS.map(f => <option key={f} value={f}>{f}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase text-gray-400 mb-1">Position</label>
                <select
                  className="w-full bg-white border border-gray-200 rounded-lg px-2 py-2 text-sm focus:outline-none"
                  value={config.position}
                  onChange={(e) => setConfig({ ...config, position: e.target.value })}
                >
                  {POSITIONS.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase text-gray-400 mb-1">Size ({config.fontSize})</label>
                <input
                  type="range"
                  min="10"
                  max="48"
                  className="w-full accent-purple-600"
                  value={config.fontSize}
                  onChange={(e) => setConfig({ ...config, fontSize: parseInt(e.target.value) })}
                />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase text-gray-400 mb-1">Shadow ({config.shadow})</label>
                <input
                  type="range"
                  min="0"
                  max="5"
                  step="0.5"
                  className="w-full accent-purple-600"
                  value={config.shadow}
                  onChange={(e) => setConfig({ ...config, shadow: parseFloat(e.target.value) })}
                />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase text-gray-400 mb-1">Stroke ({config.outline})</label>
                <input
                  type="range"
                  min="0"
                  max="5"
                  step="0.5"
                  className="w-full accent-purple-600"
                  value={config.outline}
                  onChange={(e) => setConfig({ ...config, outline: parseFloat(e.target.value) })}
                />
              </div>
            </div>
          </div>
        </Card>

        {error && (
          <div className="p-4 bg-red-50 border border-red-100 rounded-xl text-red-600 text-sm font-medium">
            ⚠️ {error}
          </div>
        )}

        <button
          onClick={handleStart}
          disabled={!file || isProcessing}
          className={`w-full py-5 rounded-xl text-white font-bold text-xl shadow-lg transition-all transform hover:scale-[1.01] active:scale-[0.99] disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none`}
          style={{ backgroundColor: COLORS.GREEN }}
        >
          {isProcessing ? 'Processing Translation...' : 'Start Translation'}
        </button>
      </div>

      {/* Right Column: Status & Outputs */}
      <div className="lg:col-span-5 space-y-6 lg:sticky lg:top-8">
        <Card title="Processing Status">
          <div className="space-y-4">
            {steps.map(step => (
              <div key={step.id} className="space-y-2">
                <div className="flex justify-between items-center text-sm">
                  <span className={`font-semibold ${step.status === 'completed' ? 'text-green-600' : step.status === 'processing' ? 'text-purple-700' : 'text-gray-500'}`}>
                    {step.label}
                  </span>
                  <span className="text-gray-400">{step.progress}%</span>
                </div>
                <ProgressBar progress={step.progress} status={step.status} />
              </div>
            ))}
          </div>
        </Card>

        <Card title="Outputs">
          {result ? (
            <div className="space-y-3">
              {result.video_output && (
                <div className="flex items-center justify-between p-4 bg-purple-50 rounded-xl border border-purple-100">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 bg-white rounded-lg text-purple-700">
                      <ICONS.Video />
                    </div>
                    <div className="overflow-hidden">
                      <p className="font-semibold text-gray-800 truncate">{result.video_output.split(/[/\\]/).pop()}</p>
                      <p className="text-xs text-gray-500">Processed Video</p>
                    </div>
                  </div>
                  <a
                    href={`/api/download?path=${encodeURIComponent(result.video_output)}`}
                    className="text-sm font-bold text-purple-700 hover:underline"
                    download
                  >
                    Download
                  </a>
                </div>
              )}
              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl border border-gray-100">
                <div className="flex items-center space-x-3 text-gray-400">
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <div className="overflow-hidden">
                    <p className="font-semibold text-gray-600 truncate">{result.output_file.split(/[/\\]/).pop()}</p>
                    <p className="text-xs">Plain text subtitles</p>
                  </div>
                </div>
                <a
                  href={`/api/download?path=${encodeURIComponent(result.output_file)}`}
                  className="text-sm font-bold text-purple-700 hover:underline"
                  download
                >
                  Download
                </a>
              </div>
            </div>
          ) : (
            <div className="text-center py-12 text-gray-400 italic">
              {isProcessing ? 'Processing... Stay tuned!' : 'Results will appear here once processing is complete'}
            </div>
          )}
        </Card>

        {isProcessing && (
          <div className="bg-white rounded-2xl p-6 border border-gray-100 shadow-sm">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-xs font-bold uppercase tracking-widest text-gray-400">Live Logs</h3>
              {!autoScrollLogs && (
                <button
                  onClick={() => setAutoScrollLogs(true)}
                  className="px-3 py-1 text-xs font-bold bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200 transition-all"
                >
                  Resume Auto-Scroll
                </button>
              )}
            </div>
            <div
              ref={logsContainerRef}
              onScroll={handleLogsScroll}
              className="font-mono text-[10px] text-gray-600 space-y-1 max-h-[348px] overflow-y-auto"
            >
              {logs.length > 0 ? (
                logs.map((log, i) => <p key={i}>{log}</p>)
              ) : (
                <p className="italic opacity-50">Waiting for process logs...</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );

};

export default Translator;

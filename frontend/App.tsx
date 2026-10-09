
import React, { useState } from 'react';
import { ViewType, AppSettings, ProcessingStep } from './types';
import Header from './components/Header';
import Translator from './components/Translator';
import Settings from './components/Settings';
import { api } from './services/api';

const SETTINGS_KEY = 'kotosub_app_settings_v1';

const DEFAULT_SETTINGS: AppSettings = {
  huggingFaceToken: '',
  outputDir: 'C:\\Videos\\Translated',
  localWhisperModel: 'large-v3-turbo',
  localLlmModel: '17slever17/translate-gemma-4-sub-e4b-GGUF',
  localLlmFile: 'translate_gemma4_sub-E4B-Q4_K_XL.gguf',
  whisperPrompt: '',
  whisperHotwords: '',
  useGpuEncoding: false,
  outputSuffix: '_translated',
  includeLanguageInName: true
};

const IDLE_STEPS: ProcessingStep[] = [
  { id: '1', label: 'Analyzing Video', progress: 0, status: 'idle' },
  { id: '2', label: 'Transcribing Audio', progress: 0, status: 'idle' },
  { id: '3', label: 'Translating', progress: 0, status: 'idle' },
  { id: '4', label: 'Embedding Subtitles', progress: 0, status: 'idle' }
];

const App: React.FC = () => {
  const [activeView, setActiveView] = useState<ViewType>(ViewType.TRANSLATOR);

  // Persistence for settings
  const [settings, setSettingsState] = useState<AppSettings>(() => {
    const saved = localStorage.getItem(SETTINGS_KEY);
    if (saved) {
      try {
        return { ...DEFAULT_SETTINGS, ...JSON.parse(saved) };
      } catch (e) {
        console.warn('Failed to parse settings from localStorage', e);
      }
    }
    return DEFAULT_SETTINGS;
  });

  // Translation State (Persistent during navigation)
  const [isProcessing, setIsProcessing] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [steps, setSteps] = useState<ProcessingStep[]>(IDLE_STEPS);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [finishedAt, setFinishedAt] = useState<number | null>(null);
  const [liveSegment, setLiveSegment] = useState<{ original: string; text: string; speaker: string | null } | null>(null);

  // Wrapper to save settings
  const onSaveSettings = (newSettings: AppSettings) => {
    setSettingsState(newSettings);
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(newSettings));
  };

  const updateStepsFromEvent = (event: any) => {
    // Map backend steps to UI step indices
    const stepIdMap: Record<string, number> = {
      'validation': 0, 'extraction': 0,
      'transcription': 1, 'diarization': 1,
      'translation': 2, 'quality_check': 2, 'refinement': 2, 'generation': 2,
      'burn_in': 3, 'completed': 3
    };

    const idx = stepIdMap[event.step];
    if (idx !== undefined) {
      setSteps(prev => {
        const next = [...prev];
        for (let i = 0; i < idx; i++) {
          next[i].status = 'completed';
          next[i].progress = 100;
        }
        next[idx].progress = event.progress;
        next[idx].status = event.status;
        if (event.step === 'completed' || event.progress === 100) {
          next[idx].status = 'completed';
        }
        return next;
      });
    }

    if (event.step === 'log' && event.message) {
      setLogs(prev => [...prev, event.message].slice(-100)); // Keep last 100 logs
    }

    if (event.segment) {
      setLiveSegment(event.segment);
    }

    if (event.step === 'completed' && event.result) {
      setResult(event.result);
    }
  };

  const startTranslation = async (file: File, config: any) => {
    setIsProcessing(true);
    setError(null);
    setResult(null);
    setLiveSegment(null);
    setStartedAt(Date.now());
    setFinishedAt(null);
    setSteps(prev => prev.map(s => ({ ...s, progress: 0, status: 'idle' })));

    try {
      await api.translateStream(
        file,
        {
          ...config,
          apiKeys: {
            huggingFace: settings.huggingFaceToken
          },
          whisperModel: settings.localWhisperModel,
          whisperPrompt: settings.whisperPrompt,
          whisperHotwords: settings.whisperHotwords,
          llmModel: settings.localLlmModel,
          localLlmFile: settings.localLlmFile,
          outputDir: settings.outputDir,
          useGpuEncoding: settings.useGpuEncoding
        },
        updateStepsFromEvent
      );
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred';
      setError(errorMessage);
      // Add error to logs so it persists
      setLogs(prev => [...prev, `❌ ERROR: ${errorMessage}`]);
    } finally {
      setIsProcessing(false);
      setFinishedAt(Date.now());
    }
  };

  const resetJob = () => {
    setResult(null);
    setError(null);
    setLiveSegment(null);
    setSteps(IDLE_STEPS);
    setStartedAt(null);
    setFinishedAt(null);
  };

  return (
    <div className="min-h-screen flex flex-col bg-surface">
      <Header activeView={activeView} onViewChange={setActiveView} />

      <main className="flex-grow container mx-auto px-4 sm:px-6 py-6 max-w-7xl">
        {activeView === ViewType.TRANSLATOR ? (
          <Translator
            settings={settings}
            isProcessing={isProcessing}
            steps={steps}
            logs={logs}
            result={result}
            error={error}
            startedAt={startedAt}
            finishedAt={finishedAt}
            liveSegment={liveSegment}
            onStart={startTranslation}
            onReset={resetJob}
          />
        ) : (
          <Settings settings={settings} onSave={onSaveSettings} />
        )}
      </main>

      <footer className="py-4 border-t border-edge text-center text-xs text-ink-faint">
        KotoSub · Experimental
      </footer>
    </div>
  );
};

export default App;

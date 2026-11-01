
import React, { useEffect, useRef, useState } from 'react';
import { ViewType, AppSettings, ProcessingStep, SubtitleConfig } from './types';
import Header from './components/Header';
import Translator from './components/Translator';
import Settings from './components/Settings';
import { Tabs, TabsContent } from '@/components/ui/tabs';
import { api, ProgressEvent } from './services/api';

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
  const [liveSegment, setLiveSegment] = useState<{ original: string; text: string; speaker: string | null } | null>(null);
  const streamErrorHandledRef = useRef(false);

  // Saved model selections are validated against the same registry Settings reads,
  // so a new model in download_models.py never needs a frontend allowlist edit.
  useEffect(() => {
    let cancelled = false;
    api.getModels()
      .then(models => {
        if (cancelled) return;
        const whisperValues = models.whisper_models.map(m => m.value);
        const llmFiles = new Set(models.llm_models.map(m => `${m.repo}/${m.file}`));
        if (!whisperValues.length || !llmFiles.size) return;
        setSettingsState(prev => {
          const whisperValid = whisperValues.includes(prev.localWhisperModel);
          const llmValid = llmFiles.has(`${prev.localLlmModel}/${prev.localLlmFile}`);
          if (whisperValid && llmValid) return prev;
          const next: AppSettings = {
            ...prev,
            localWhisperModel: whisperValid ? prev.localWhisperModel : DEFAULT_SETTINGS.localWhisperModel,
            localLlmModel: llmValid ? prev.localLlmModel : DEFAULT_SETTINGS.localLlmModel,
            localLlmFile: llmValid ? prev.localLlmFile : DEFAULT_SETTINGS.localLlmFile
          };
          localStorage.setItem(SETTINGS_KEY, JSON.stringify(next));
          return next;
        });
      })
      .catch(e => console.warn('Could not validate saved models against /api/models', e));
    return () => { cancelled = true; };
  }, []);

  // Wrapper to save settings
  const onSaveSettings = (newSettings: AppSettings) => {
    setSettingsState(newSettings);
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(newSettings));
  };

  const updateStepsFromEvent = (event: ProgressEvent) => {
    if (event.status === 'error') {
      // C4 error event: surface the message, freeze the active step as failed.
      streamErrorHandledRef.current = true;
      setError(event.message);
      setLogs(prev => [...prev, `❌ ERROR: ${event.message}`]);
      setSteps(prev => {
        const active = prev.findIndex(s => s.status === 'processing');
        if (active === -1) return prev;
        const next = [...prev];
        next[active] = { ...next[active], status: 'error' };
        return next;
      });
      return;
    }

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

  const startTranslation = async (file: File, config: SubtitleConfig) => {
    streamErrorHandledRef.current = false;
    setIsProcessing(true);
    setError(null);
    setResult(null);
    setLiveSegment(null);
    setStartedAt(Date.now());
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
          useGpuEncoding: settings.useGpuEncoding,
          outputSuffix: settings.outputSuffix,
          includeLanguageInName: settings.includeLanguageInName
        },
        updateStepsFromEvent
      );
    } catch (err) {
      // api.translateStream already emitted a synthetic error event for stream
      // failures; avoid duplicating the message in that case.
      if (!streamErrorHandledRef.current) {
        const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred';
        setError(errorMessage);
        // Add error to logs so it persists
        setLogs(prev => [...prev, `❌ ERROR: ${errorMessage}`]);
      }
    } finally {
      setIsProcessing(false);
    }
  };

  const resetJob = () => {
    setResult(null);
    setError(null);
    setLiveSegment(null);
    setSteps(IDLE_STEPS);
    setStartedAt(null);
  };

  return (
    <Tabs
      value={activeView}
      onValueChange={(v) => setActiveView(v as ViewType)}
      className="min-h-screen gap-0 bg-background"
    >
      <Header />

      <main className="flex-grow container mx-auto px-4 sm:px-6 py-6 max-w-7xl">
        <TabsContent value={ViewType.TRANSLATOR}>
          <Translator
            settings={settings}
            isProcessing={isProcessing}
            steps={steps}
            logs={logs}
            result={result}
            error={error}
            startedAt={startedAt}
            liveSegment={liveSegment}
            onStart={startTranslation}
            onReset={resetJob}
          />
        </TabsContent>
        <TabsContent value={ViewType.SETTINGS}>
          <Settings settings={settings} onSave={onSaveSettings} />
        </TabsContent>
      </main>

      <footer className="border-t py-4 text-center text-xs text-muted-foreground">
        KotoSub · Experimental
      </footer>
    </Tabs>
  );
};

export default App;


import React, { useState } from 'react';
import { ViewType, AppSettings, ProcessingStep } from './types';
import Header from './components/Header';
import Translator from './components/Translator';
import Settings from './components/Settings';
import { api } from './services/api';
import { COLORS } from './constants';

const SETTINGS_KEY = 'kotosub_app_settings_v1';

const App: React.FC = () => {
  const [activeView, setActiveView] = useState<ViewType>(ViewType.TRANSLATOR);

  // Persistence for settings
  const [settings, setSettingsState] = useState<AppSettings>(() => {
    const saved = localStorage.getItem(SETTINGS_KEY);
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {
        console.warn('Failed to parse settings from localStorage', e);
      }
    }
    return {
      apiKey: '',
      baseUrl: 'https://proxy.fuelix.ai',
      huggingFaceToken: '',
      whisperModel: 'whisper-large-v3',
      llmModel: 'gemini-3-flash-preview',
      outputDir: 'C:\\Videos\\Translated',
      transcriptionProvider: 'openai',
      translationProvider: 'openai',
      localWhisperModel: 'medium',
      localLlmModel: 'Qwen/Qwen3-8B-GGUF',
      localLlmFile: 'Qwen3-8B-Q4_K_M.gguf',
      useGpuEncoding: false,
      processingMode: 'cloud',
      outputSuffix: '_translated',
      includeLanguageInName: true
    };
  });

  // Migration for stale settings (TheBloke repo changes)
  React.useEffect(() => {
    let updated = false;
    const newSettings = { ...settings };

    if (newSettings.localLlmModel === 'TheBloke/Mistral-7B-Instruct-v0.2-GGUF') {
      newSettings.localLlmModel = 'Qwen/Qwen3-8B-GGUF';
      newSettings.localLlmFile = 'Qwen3-8B-Q4_K_M.gguf';
      updated = true;
    }
    if (newSettings.localLlmModel === 'bartowski/Meta-Llama-3-8B-Instruct-GGUF') {
      newSettings.localLlmModel = 'Qwen/Qwen3-8B-GGUF';
      newSettings.localLlmFile = 'Qwen3-8B-Q4_K_M.gguf';
      updated = true;
    }

    if (updated) {
      console.log('Migrating stale model repository settings...');
      onSaveSettings(newSettings);
    }
  }, []);

  // Translation State (Persistent during navigation)
  const [isProcessing, setIsProcessing] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [steps, setSteps] = useState<ProcessingStep[]>([
    { id: '1', label: 'Video Analysis', progress: 0, status: 'idle' },
    { id: '2', label: 'Transcription', progress: 0, status: 'idle' },
    { id: '3', label: 'Translation', progress: 0, status: 'idle' },
    { id: '4', label: 'Subtitles Burn-in', progress: 0, status: 'idle' }
  ]);

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

    if (event.step === 'completed' && event.result) {
      setResult(event.result);
    }
    if (event.job_id) {
      setActiveJobId(event.job_id);
    }
  };

  const startTranslation = async (file: File, config: any) => {
    setIsProcessing(true);
    setError(null);
    setResult(null);
    // Don't clear logs - preserve them from previous runs for debugging
    // setLogs([]);
    setSteps(prev => prev.map(s => ({ ...s, progress: 0, status: 'idle' })));

    try {
      await api.translateStream(
        file,
        {
          ...config,
          apiKeys: {
            openai: settings.apiKey,
            huggingFace: settings.huggingFaceToken
          },
          baseUrl: settings.baseUrl,
          whisperModel: settings.transcriptionProvider === 'local' ? settings.localWhisperModel : settings.whisperModel,
          llmModel: settings.translationProvider === 'local' ? settings.localLlmModel : settings.llmModel,
          localLlmFile: settings.localLlmFile,
          outputDir: settings.outputDir,
          transcriptionProvider: settings.transcriptionProvider,
          translationProvider: settings.translationProvider,
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
    }
  };

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: COLORS.BG_GRAY }}>
      <Header activeView={activeView} onViewChange={setActiveView} />

      <main className="flex-grow container mx-auto px-4 py-8 max-w-7xl">
        {activeView === ViewType.TRANSLATOR ? (
          <Translator
            settings={settings}
            isProcessing={isProcessing}
            steps={steps}
            logs={logs}
            result={result}
            error={error}
            onStart={startTranslation}
          />
        ) : (
          <Settings settings={settings} onSave={onSaveSettings} />
        )}
      </main>

      <footer className="py-6 border-t border-gray-200 text-center text-sm text-gray-500">
        <p>KotoSub • Experimental Tool</p>
        <div className="mt-2 flex justify-center space-x-4">
          <span className="cursor-pointer hover:text-purple-700">Documentation</span>
          <span className="cursor-pointer hover:text-purple-700">Support</span>
          <span className="cursor-pointer hover:text-purple-700">API Access</span>
        </div>
      </footer>
    </div>
  );
};

export default App;

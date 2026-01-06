
import React from 'react';
import { AppSettings } from '../types';
import { COLORS, LOCAL_LLM_MODELS } from '../constants';
import Card from './Card';

import { api } from '../services/api';

interface SettingsProps {
  settings: AppSettings;
  onSave: (settings: AppSettings) => void;
}

const Settings: React.FC<SettingsProps> = ({ settings, onSave }) => {
  const [llmModels, setLlmModels] = React.useState(LOCAL_LLM_MODELS.map(m => ({ ...m, installed: false })));
  const [whisperModels, setWhisperModels] = React.useState<{ label: string, value: string, installed: boolean }[]>([]);

  React.useEffect(() => {
    api.getModels().then(data => {
      setLlmModels(data.llm_models);
      setWhisperModels(data.whisper_models);
    }).catch(err => console.error("Failed to load models", err));
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    onSave({ ...settings, [e.target.name]: e.target.value });
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="mb-8">
        <h2 className="text-3xl font-bold mb-2" style={{ color: COLORS.PURPLE }}>App Configuration</h2>
        <p className="text-gray-500">Manage your API tokens and default processing parameters.</p>
      </div>

      <div className="bg-white p-6 rounded-xl border border-gray-200 shadow-sm mb-8 flex flex-col md:flex-row items-center justify-between gap-4">
        <div>
          <h3 className="text-lg font-bold text-gray-800">Processing Mode</h3>
          <p className="text-sm text-gray-500">Choose between Cloud APIs (Quality, slower) or Local GPU (Private, faster).</p>
        </div>

        <div className="flex bg-gray-100 p-1 rounded-lg">
          <button
            className={`px-6 py-2 rounded-md text-sm font-bold transition-all ${settings.processingMode === 'cloud' ? 'bg-white text-purple-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
            onClick={() => {
              onSave({
                ...settings,
                processingMode: 'cloud',
                transcriptionProvider: 'openai',
                translationProvider: 'openai'
              });
            }}
          >
            Cloud AI
          </button>
          <button
            className={`px-6 py-2 rounded-md text-sm font-bold transition-all ${settings.processingMode === 'local' ? 'bg-white text-purple-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
            onClick={() => {
              onSave({
                ...settings,
                processingMode: 'local',
                transcriptionProvider: 'local',
                translationProvider: 'local'
              });
            }}
          >
            Local Mode (GPU)
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        {settings.processingMode === 'cloud' && (
          <Card title="AI Provider Access">
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">API Key</label>
                <input
                  type="password"
                  name="apiKey"
                  value={settings.apiKey}
                  onChange={handleChange}
                  placeholder="sk-..."
                  className="w-full bg-white border border-gray-200 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500 transition-all"
                />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">AI Router</label>
                <div className="space-y-2">
                  <select
                    className="w-full bg-white border border-gray-200 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500 transition-all"
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val === 'fuelix') onSave({ ...settings, baseUrl: 'https://proxy.fuelix.ai' });
                      else if (val === 'openrouter') onSave({ ...settings, baseUrl: 'https://openrouter.ai/api/v1' });
                    }}
                    defaultValue={settings.baseUrl.includes('fuelix') ? 'fuelix' : settings.baseUrl.includes('openrouter') ? 'openrouter' : 'custom'}
                  >
                    <option value="fuelix">FueliX (Default)</option>
                    <option value="openrouter">OpenRouter</option>
                    <option value="custom">Custom Endpoint</option>
                  </select>

                  <input
                    type="text"
                    name="baseUrl"
                    value={settings.baseUrl}
                    onChange={handleChange}
                    placeholder="https://..."
                    className="w-full bg-white border border-gray-200 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500 transition-all text-sm text-gray-600"
                  />
                </div>
              </div>
            </div>
          </Card>
        )}

        <Card title="Integration Tokens">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Hugging Face Token</label>
            <input
              type="password"
              name="huggingFaceToken"
              value={settings.huggingFaceToken}
              onChange={handleChange}
              placeholder="hf_..."
              className="w-full bg-white border border-gray-200 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500 transition-all"
            />
            <p className="mt-2 text-xs text-gray-400 italic">Required for Speaker Diarization</p>
          </div>
        </Card>
      </div>

      {settings.processingMode === 'local' && (
        <Card title="Local Processing (GPU)">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Local Whisper Model</label>
                <select
                  className="w-full bg-white border border-gray-200 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500 transition-all"
                  name="localWhisperModel"
                  value={settings.localWhisperModel}
                  onChange={handleChange}
                >
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
                    </>
                  )}
                </select>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Local LLM Model</label>
                <select
                  className="w-full bg-white border border-gray-200 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500 transition-all font-medium"
                  name="localLlmModel"
                  value={settings.localLlmModel}
                  onChange={(e) => {
                    const selected = llmModels.find(m => m.repo === e.target.value);
                    if (selected) {
                      onSave({
                        ...settings,
                        localLlmModel: selected.repo,
                        localLlmFile: selected.file
                      });
                    }
                  }}
                >
                  {llmModels.map(m => (
                    <option key={m.repo} value={m.repo}>
                      {m.label} {m.installed ? '(Installed)' : '(Missing)'}
                    </option>
                  ))}
                </select>
                <p className="mt-2 text-xs text-gray-400 italic">
                  Currently selected file: <span className="font-mono text-purple-600 font-bold">{settings.localLlmFile}</span>
                </p>
                <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                  <p className="text-xs font-semibold text-blue-700 mb-1">💡 Model Recommendation</p>
                  <p className="text-xs text-blue-600">
                    {settings.localLlmModel.toLowerCase().includes('qwen') && '✓ Qwen 3 excels at Chinese, Japanese, and Korean translations with strong multilingual support.'}
                    {settings.localLlmModel.toLowerCase().includes('gemma') && '✓ Gemma 2 offers fast, balanced performance for European languages.'}
                    {settings.localLlmModel.toLowerCase().includes('openhermes') && '✓ OpenHermes provides high-quality translations with minimal filtering.'}
                    {settings.localLlmModel.toLowerCase().includes('dolphin') && '✓ Dolphin is uncensored and works well for creative/informal content.'}
                    {settings.localLlmModel.toLowerCase().includes('noromaid') && '✓ Noromaid specializes in creative writing and NSFW content translation.'}
                  </p>
                </div>
              </div>
            </div>

            <div className="md:col-span-2">
              <label className="flex items-center space-x-3 cursor-pointer p-4 bg-gray-50 rounded-lg border border-gray-100">
                <input
                  type="checkbox"
                  className="w-5 h-5 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                  checked={settings.useGpuEncoding}
                  onChange={(e) => onSave({ ...settings, useGpuEncoding: e.target.checked })}
                />
                <div className="flex flex-col">
                  <span className="font-medium text-gray-700">Use Hardware Acceleration (NVENC)</span>
                  <span className="text-xs text-gray-400 italic">Uses GPU for video encoding (HEVC). Faster but requires NVIDIA GPU.</span>
                </div>
              </label>
            </div>
          </div>
        </Card>
      )}


      <Card title="Export & Naming">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Filename Suffix</label>
            <input
              type="text"
              name="outputSuffix"
              value={settings.outputSuffix}
              onChange={handleChange}
              placeholder="_translated"
              className="w-full bg-white border border-gray-200 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500 transition-all font-mono"
            />
            <p className="mt-2 text-xs text-gray-400 italic">Example: original{settings.outputSuffix}.srt</p>
          </div>

          <div className="flex items-center">
            <label className="flex items-center space-x-3 cursor-pointer p-2 w-full">
              <input
                type="checkbox"
                className="w-5 h-5 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                checked={settings.includeLanguageInName}
                onChange={(e) => onSave({ ...settings, includeLanguageInName: e.target.checked })}
              />
              <div className="flex flex-col">
                <span className="font-medium text-gray-700">Include Language Code</span>
                <span className="text-xs text-gray-400 italic">Append _en to the filename.</span>
              </div>
            </label>
          </div>
        </div>
      </Card>

      <Card title="System Defaults">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {settings.processingMode === 'cloud' && (
            <>
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Whisper Model</label>
                <input
                  type="text"
                  name="whisperModel"
                  value={settings.whisperModel}
                  onChange={handleChange}
                  placeholder="whisper-large-v3"
                  className="w-full bg-white border border-gray-200 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">LLM Model</label>
                <input
                  type="text"
                  name="llmModel"
                  value={settings.llmModel}
                  onChange={handleChange}
                  placeholder="gemini-2.0-flash-exp"
                  className="w-full bg-white border border-gray-200 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
              </div>
            </>
          )}
          <div className={settings.processingMode === 'local' ? "col-span-3" : ""}>
            <label className="block text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">Output Directory</label>
            <input
              type="text"
              name="outputDir"
              value={settings.outputDir}
              onChange={handleChange}
              className="w-full bg-white border border-gray-200 rounded-lg px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500 transition-all"
            />
          </div>
        </div>
      </Card>

      <div className="pt-4 flex justify-end">
        <button
          className="px-12 py-4 rounded-xl text-white font-bold text-lg shadow-lg transition-all hover:scale-[1.02] active:scale-[0.98]"
          style={{ backgroundColor: COLORS.PURPLE }}
          onClick={() => alert('Settings saved successfully!')}
        >
          Save Configuration
        </button>
      </div>
    </div>
  );
};

export default Settings;


import React from 'react';
import { AppSettings } from '../types';
import { COLORS } from '../constants';
import Card from './Card';

interface SettingsProps {
  settings: AppSettings;
  onSave: (settings: AppSettings) => void;
}

const Settings: React.FC<SettingsProps> = ({ settings, onSave }) => {
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    onSave({ ...settings, [e.target.name]: e.target.value });
  };

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div className="mb-8">
        <h2 className="text-3xl font-bold mb-2" style={{ color: COLORS.PURPLE }}>App Configuration</h2>
        <p className="text-gray-500">Manage your API tokens and default processing parameters.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
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

      <Card title="System Defaults">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
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
          <div>
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

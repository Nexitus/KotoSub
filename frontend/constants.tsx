
import React from 'react';

export const COLORS = {
  PURPLE: '#4B286D',
  GREEN: '#2B8000',
  LIGHT_GREEN: '#66CC00',
  BG_GRAY: '#F7F8FA',
  TEXT_DARK: '#2A2C2E',
  TEXT_LIGHT: '#54595F'
};

export const SOURCE_LANGUAGES = [
  { label: 'Auto-detect', value: 'auto' },
  { label: 'English', value: 'en' },
  { label: 'Japanese', value: 'ja' },
  { label: 'Korean', value: 'ko' },
  { label: 'Mandarin (Chinese)', value: 'zh' },
  { label: 'Taiwanese', value: 'zh' }, // Mapping to zh as Whisper handles it generally
  { label: 'Spanish', value: 'es' },
  { label: 'Portuguese', value: 'pt' },
  { label: 'French', value: 'fr' },
  { label: 'German', value: 'de' },
  { label: 'Italian', value: 'it' },
  { label: 'Dutch', value: 'nl' },
  { label: 'Russian', value: 'ru' },
  { label: 'Polish', value: 'pl' },
  { label: 'Ukrainian', value: 'uk' },
  { label: 'Czech', value: 'cs' },
  { label: 'Slovak', value: 'sk' },
  { label: 'Hungarian', value: 'hu' },
  { label: 'Romanian', value: 'ro' },
  { label: 'Bulgarian', value: 'bg' },
  { label: 'Croatian', value: 'hr' },
  { label: 'Serbian', value: 'sr' },
  { label: 'Slovenian', value: 'sl' },
  { label: 'Greek', value: 'el' },
  { label: 'Turkish', value: 'tr' },
  { label: 'Swedish', value: 'sv' },
  { label: 'Danish', value: 'da' },
  { label: 'Norwegian', value: 'no' },
  { label: 'Finnish', value: 'fi' },
];

export const TARGET_LANGUAGES = [
  { label: 'English', value: 'en' }
];

export const FONTS = [
  'Helvetica',
  'Arial',
  'Roboto',
  'Inter',
  'Circular'
];

export const POSITIONS = [
  'Bottom Center',
  'Bottom Left',
  'Bottom Right',
  'Top Center'
];

export const ICONS = {
  Video: () => (
    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
    </svg>
  ),
  Settings: () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  ),
  Translate: () => (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5h12M9 3v2m1.048 9.5A18.022 18.022 0 016.412 9m6.088 9h7M11 21l5-10 5 10M12.751 5C11.783 10.77 8.07 15.61 3 18.129" />
    </svg>
  )
};

export const LOCAL_LLM_MODELS = [
  {
    label: 'Qwen 3 8B (Strong/Chinese-Native)',
    repo: 'Qwen/Qwen3-8B-GGUF',
    file: 'Qwen3-8B-Q4_K_M.gguf'
  },
  {
    label: 'Dolphin 2.8 Mistral (Uncensored)',
    repo: 'mradermacher/dolphin-2.8-mistral-7b-v02-GGUF',
    file: 'dolphin-2.8-mistral-7b-v02.Q4_K_M.gguf'
  },
  {
    label: 'Noromaid 7B v0.4 (Creative/NSFW)',
    repo: 'NeverSleep/Noromaid-7B-0.4-DPO-GGUF',
    file: 'Noromaid-7B-0.4-DPO.q4_k_m.gguf'
  },
  {
    label: 'OpenHermes 2.5 (High Quality/Low Filter)',
    repo: 'TheBloke/OpenHermes-2.5-Mistral-7B-GGUF',
    file: 'openhermes-2.5-mistral-7b.Q4_K_M.gguf'
  },
  {
    label: 'Gemma 2 9B (Google/Fast)',
    repo: 'bartowski/gemma-2-9b-it-GGUF',
    file: 'gemma-2-9b-it-Q4_K_M.gguf'
  }
];
export const SUBTITLE_FORMATS = [
  { label: 'SRT (Standard)', value: 'srt' },
  { label: 'ASS (Advanced Stylized)', value: 'ass' },
  { label: 'VTT (Web Player Compatible)', value: 'vtt' }
];

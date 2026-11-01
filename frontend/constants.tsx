

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
export const SUBTITLE_FORMATS = [
  { label: 'SRT (Standard)', value: 'srt' },
  { label: 'ASS (Advanced Stylized)', value: 'ass' },
  { label: 'VTT (Web Player Compatible)', value: 'vtt' }
];

export const LOOKAHEAD_PRESETS = [
  { label: '15s — Minimal Latency', value: 15 },
  { label: '30s — Balanced (Recommended)', value: 30 },
  { label: '60s — Conservative', value: 60 },
];


export enum ViewType {
  TRANSLATOR = 'translator',
  SETTINGS = 'settings'
}

export interface SubtitleConfig {
  sourceLang: string;
  targetLang: string;
  enableDiarization: boolean;
  qualityVerification: boolean;
  burnSubtitles: boolean;
  font: string;
  fontSize: number;
  position: string;
  shadow: number;
  outline: number;
}

export interface ProcessingStep {
  id: string;
  label: string;
  progress: number;
  status: 'idle' | 'processing' | 'completed' | 'error';
}

export interface AppSettings {
  apiKey: string;
  baseUrl: string;
  huggingFaceToken: string;
  whisperModel: string;
  llmModel: string;
  outputDir: string;
}

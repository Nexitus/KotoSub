
export enum ViewType {
  TRANSLATOR = 'translator',
  SETTINGS = 'settings',
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
  subtitleFormat: 'srt' | 'ass' | 'vtt';
  // Extras merged into the config payload when posting to /api/translate_stream
  apiKeys?: { huggingFace?: string };
  whisperModel?: string;
  whisperPrompt?: string;
  whisperHotwords?: string;
  llmModel?: string;
  localLlmFile?: string;
  outputDir?: string;
  useGpuEncoding?: boolean;
  outputSuffix?: string;
  includeLanguageInName?: boolean;
}

export interface ProcessingStep {
  id: string;
  label: string;
  progress: number;
  status: 'idle' | 'processing' | 'completed' | 'error';
}

export interface AppSettings {
  huggingFaceToken: string;
  outputDir: string;
  localWhisperModel: string;
  localLlmModel: string;
  localLlmFile: string;
  whisperPrompt: string;
  whisperHotwords: string;
  useGpuEncoding: boolean;
  outputSuffix: string;
  includeLanguageInName: boolean;
}

export interface LiveSegment {
  start: number;
  end: number;
  text: string;
  original: string;
  speaker: string | null;
}

export interface LiveStatusResponse {
  session_id: string;
  state: string;
  current_position: number;
  duration: number;
  filepath: string | null;
  filename: string | null;
  buffer_health_seconds: number;
  processed_until: number;
  segments: LiveSegment[];
  new_segment_count: number;
  srt_file_path: string | null;
  remuxed: boolean;
  hls: boolean;
  playlist_ready: boolean;
  transcoding: boolean;
  transcode_progress: number;
  transcode_error: string | null;
  models_loading: boolean;
  logs: string[];
  error: string | null;
}

export interface LiveSessionConfig {
  video_path?: string;
  source_lang: string;
  target_lang: string;
  lookahead_seconds: number;
  whisper_model?: string;
  llm_model?: string;
  local_llm_file?: string;
}

export interface LiveStartResponse {
  session_id: string;
  video_path: string;
  duration: number;
  remuxed: boolean;
  transcoding: boolean; // returned by backend; missing in older backend versions
  hls: boolean; // playback served via HLS event playlist (needs conversion)
}

import { LiveSessionConfig, LiveStartResponse, LiveStatusResponse, SubtitleConfig } from '../types';

export type ProcessingStatus = 'idle' | 'processing' | 'completed' | 'error';

export interface ProgressEvent {
    step: string;     // Logic step mapping (1=Analysis, 2=Transcription, etc)
    progress: number; // 0-100
    message: string;
    status: ProcessingStatus;
    result?: any;     // Final result payload on completion
    segment?: {       // Latest translated segment during the translation step
        original: string;
        text: string;
        speaker: string | null;
    };
}

export const API_BASE = ''; // Relative path since we serve from same origin

export const api = {
    /**
     * Upload video and start streaming translation process
     */
    translateStream: async (
        file: File,
        config: SubtitleConfig,
        onProgress: (event: ProgressEvent) => void
    ): Promise<void> => {
        const formData = new FormData();
        formData.append('video', file);
        formData.append('config', JSON.stringify(config));

        try {
            const response = await fetch(`${API_BASE}/api/translate_stream`, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                throw new Error(`Upload failed: ${response.statusText}`);
            }

            if (!response.body) {
                throw new Error('No response body received');
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });

                // Process line by line for NDJSON
                const lines = buffer.split('\n');
                buffer = lines.pop() || ''; // Keep incomplete line in buffer

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const event = JSON.parse(line) as ProgressEvent;
                        onProgress(event);
                    } catch (e) {
                        console.warn('Failed to parse progress event:', line);
                    }
                }
            }
        } catch (error) {
            console.error('Streaming error:', error);
            onProgress({
                step: 'error',
                progress: 0,
                message: error instanceof Error ? error.message : 'Unknown error',
                status: 'error'
            });
            throw error;
        }
    },

    /**
     * Fetch available models from backend
     */
    getModels: async (): Promise<{
        llm_models: Array<{ label: string; repo: string; file: string; installed: boolean; recommended_for?: string[] }>;
        whisper_models: Array<{ label: string; value: string; installed: boolean }>;
        recommended: Record<string, string>;
    }> => {
        const response = await fetch(`${API_BASE}/api/models`);
        if (!response.ok) {
            throw new Error('Failed to fetch models');
        }
        return response.json();
    },

    /**
     * Start background downloads for MISSING models of a kind
     * ("llm" | "whisper" | "qwen" | "all"). Poll status with modelDownloadStatus.
     */
    downloadModels: async (kind: string): Promise<{ started: boolean; kind: string }> => {
        const response = await fetch(`${API_BASE}/api/models/download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ kind }),
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Download start failed: ${response.statusText}`);
        }
        return response.json();
    },

    modelDownloadStatus: async (): Promise<{
        active: boolean;
        kind: string | null;
        logs: string[];
        error: string | null;
        finished: boolean;
    }> => {
        const response = await fetch(`${API_BASE}/api/models/download/status`);
        if (!response.ok) throw new Error(`Download status failed: ${response.statusText}`);
        return response.json();
    },

    getGpuInfo: async (): Promise<{
        available: boolean;
        name: string | null;
        vram_total_mb: number | null;
        detected_gpu: boolean;
    }> => {
        try {
            const response = await fetch(`${API_BASE}/api/gpu-info`);
            if (!response.ok) return { available: false, name: null, vram_total_mb: null, detected_gpu: false };
            return response.json();
        } catch {
            return { available: false, name: null, vram_total_mb: null, detected_gpu: false };
        }
    },

    liveStart: async (config: LiveSessionConfig): Promise<LiveStartResponse> => {
        const response = await fetch(`${API_BASE}/api/live/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config),
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Live start failed: ${response.statusText}`);
        }
        return response.json();
    },

    liveStartUpload: async (file: File, config: LiveSessionConfig): Promise<LiveStartResponse> => {
        const formData = new FormData();
        formData.append('video', file);
        formData.append('config', JSON.stringify(config));
        const response = await fetch(`${API_BASE}/api/live/start_upload`, {
            method: 'POST',
            body: formData,
        });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Upload failed: ${response.statusText}`);
        }
        return response.json();
    },

    liveStatus: async (sessionId: string, position?: number, state?: string): Promise<LiveStatusResponse> => {
        const params = new URLSearchParams();
        if (position !== undefined) params.set('position', position.toString());
        if (state) params.set('state', state);
        const qs = params.toString();
        const response = await fetch(`${API_BASE}/api/live/status/${sessionId}${qs ? '?' + qs : ''}`);
        if (!response.ok) throw new Error(`Status fetch failed: ${response.statusText}`);
        return response.json();
    },

    liveStop: async (sessionId: string): Promise<{ srt_file_path: string }> => {
        const response = await fetch(`${API_BASE}/api/live/stop/${sessionId}`, {
            method: 'POST',
        });
        if (!response.ok) throw new Error(`Stop failed: ${response.statusText}`);
        return response.json();
    },
};

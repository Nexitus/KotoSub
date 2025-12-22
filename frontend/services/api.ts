export interface TranslatorConfig {
    sourceLang: string;
    targetLang: string;
    enableDiarization: boolean;
    qualityVerification: boolean;
    burnSubtitles: boolean;
    font?: string;
    fontSize?: number;
    position?: string;
    apiKeys?: {
        openai?: string;
        huggingFace?: string;
    };
    baseUrl?: string;
    whisperModel?: string;
    llmModel?: string;
    outputDir?: string;
}

export type ProcessingStatus = 'idle' | 'processing' | 'completed' | 'error';

export interface ProgressEvent {
    step: string;     // Logic step mapping (1=Analysis, 2=Transcription, etc)
    progress: number; // 0-100
    message: string;
    status: ProcessingStatus;
    result?: any;     // Final result payload on completion
}

export const API_BASE = ''; // Relative path since we serve from same origin

export const api = {
    /**
     * Upload video and start streaming translation process
     */
    translateStream: async (
        file: File,
        config: TranslatorConfig,
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
    }
};

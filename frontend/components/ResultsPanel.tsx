import React from 'react';
import { ICONS } from '../constants';

interface TranslationResult {
  video_output?: string;
  output_file: string;
}

interface ResultsPanelProps {
  result: TranslationResult;
  onReset: () => void;
}

const fileName = (path: string) => path.split(/[/\\]/).pop() ?? path;

const ResultsPanel: React.FC<ResultsPanelProps> = ({ result, onReset }) => {
  return (
    <div className="space-y-3 enter-slide-up">
      <div className="flex items-center gap-2 px-1">
        <span className="p-1 rounded-full bg-success/15 text-success">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
          </svg>
        </span>
        <p className="text-sm font-bold text-ink">Your files are ready</p>
      </div>

      {result.video_output && (
        <div className="flex items-center justify-between gap-3 p-4 bg-brand-soft/60 rounded-xl border border-brand/20">
          <div className="flex items-center gap-3 min-w-0">
            <div className="p-2 bg-raised rounded-lg text-brand shrink-0">
              <ICONS.Video />
            </div>
            <div className="overflow-hidden">
              <p className="font-semibold text-ink truncate text-sm">{fileName(result.video_output)}</p>
              <p className="text-xs text-ink-faint">Translated video</p>
            </div>
          </div>
          <a
            href={`/api/download?path=${encodeURIComponent(result.video_output)}`}
            className="shrink-0 inline-flex items-center gap-1.5 text-sm font-bold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 rounded"
            download
          >
            <ICONS.Download />
            Download
          </a>
        </div>
      )}

      <div className="flex items-center justify-between gap-3 p-4 bg-raised rounded-xl border border-edge">
        <div className="flex items-center gap-3 text-ink-soft min-w-0">
          <div className="p-2 bg-edge/70 rounded-lg text-ink-soft shrink-0">
            <ICONS.Document />
          </div>
          <div className="overflow-hidden">
            <p className="font-semibold text-ink truncate text-sm">{fileName(result.output_file)}</p>
            <p className="text-xs text-ink-faint">Subtitle file</p>
          </div>
        </div>
        <a
          href={`/api/download?path=${encodeURIComponent(result.output_file)}`}
          className="shrink-0 inline-flex items-center gap-1.5 text-sm font-bold text-brand hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 rounded"
          download
        >
          <ICONS.Download />
          Download
        </a>
      </div>

      <button
        onClick={onReset}
        className="w-full py-3 rounded-xl border border-edge text-ink-soft font-semibold text-sm hover:bg-edge/40 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-2"
      >
        Translate another video
      </button>
    </div>
  );
};

export default ResultsPanel;

import React from 'react';
import { CircleCheck, Download, FileText, Video } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface TranslationResult {
  downloads: {
    subtitle: string;
    video: string | null;
  };
}

interface ResultsPanelProps {
  result: TranslationResult;
  onReset: () => void;
}

const ResultsPanel: React.FC<ResultsPanelProps> = ({ result, onReset }) => {
  return (
    <div className="space-y-3 enter-slide-up">
      <div className="flex items-center gap-2 px-1">
        <span className="p-1 rounded-full bg-success/15 text-success">
          <CircleCheck className="size-4" aria-hidden="true" />
        </span>
        <p className="text-sm font-bold text-foreground">Your files are ready</p>
      </div>

      {result.downloads.video && (
        <div className="flex items-center justify-between gap-3 rounded-lg border bg-muted/50 p-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className="shrink-0 rounded-md bg-background p-2 text-foreground">
              <Video className="size-5" />
            </div>
            <div className="overflow-hidden">
              <p className="font-semibold text-foreground truncate text-sm">Translated video</p>
              <p className="text-xs text-muted-foreground">Video with burned-in subtitles</p>
            </div>
          </div>
          <Button asChild size="sm" variant="outline">
            <a href={`/api/download?token=${encodeURIComponent(result.downloads.video)}`} download>
              <Download />
              Download
            </a>
          </Button>
        </div>
      )}

      <div className="flex items-center justify-between gap-3 rounded-lg border p-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="shrink-0 rounded-md bg-muted p-2 text-muted-foreground">
            <FileText className="size-5" />
          </div>
          <div className="overflow-hidden">
            <p className="font-semibold text-foreground truncate text-sm">Subtitle file</p>
            <p className="text-xs text-muted-foreground">Timed subtitles for your video</p>
          </div>
        </div>
        <Button asChild size="sm" variant="outline">
          <a href={`/api/download?token=${encodeURIComponent(result.downloads.subtitle)}`} download>
            <Download />
            Download
          </a>
        </Button>
      </div>

      <Button variant="outline" className="w-full" onClick={onReset}>
        Translate another video
      </Button>
    </div>
  );
};

export default ResultsPanel;

import React from 'react';

interface ProgressBarProps {
  progress: number;
  status: 'idle' | 'processing' | 'completed' | 'error';
  thin?: boolean;
}

const FILL_COLORS: Record<ProgressBarProps['status'], string> = {
  completed: 'var(--success)',
  error: 'var(--error)',
  processing: 'var(--brand)',
  idle: 'var(--edge-strong)',
};

const ProgressBar: React.FC<ProgressBarProps> = ({ progress, status, thin = false }) => {
  return (
    <div
      className={`w-full bg-edge/60 rounded-full overflow-hidden ${thin ? 'h-1.5' : 'h-2.5'}`}
      role="progressbar"
      aria-valuenow={progress}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className="h-full rounded-full transition-all duration-500 ease-out"
        style={{ width: `${progress}%`, backgroundColor: FILL_COLORS[status] }}
      />
    </div>
  );
};

export default ProgressBar;

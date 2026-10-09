import React, { useEffect, useState } from 'react';
import { ProcessingStep } from '../types';
import ProgressBar from './ProgressBar';

const STEP_ICONS: Record<ProcessingStep['status'], string> = {
  idle: '○',
  processing: '◔',
  completed: '✓',
  error: '✗',
};

const STEP_LABEL_COLORS: Record<ProcessingStep['status'], string> = {
  completed: 'text-success',
  error: 'text-error',
  processing: 'text-brand',
  idle: 'text-ink-faint',
};

interface StepRailProps {
  steps: ProcessingStep[];
  startedAt: number | null;
  finishedAt: number | null;
  failed: boolean;
}

const formatDuration = (ms: number) => {
  const totalSec = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;
  if (h > 0) return `${h}h ${m}m ${s}s`;
  return `${m}m ${s.toString().padStart(2, '0')}s`;
};

const StepRail: React.FC<StepRailProps> = ({ steps, startedAt, finishedAt, failed }) => {
  const [now, setNow] = useState(() => Date.now());
  const running = startedAt !== null && finishedAt === null;

  useEffect(() => {
    if (!running) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [running]);

  const anyError = failed || steps.some(s => s.status === 'error');
  const allDone = steps.every(s => s.status === 'completed');
  const overallStatus: ProcessingStep['status'] = anyError ? 'error' : allDone ? 'completed' : 'processing';
  const overall = Math.min(
    100,
    Math.round(steps.reduce((acc, s) => acc + s.progress, 0) / Math.max(steps.length, 1))
  );

  const elapsed = (() => {
    if (startedAt === null) return null;
    if (finishedAt !== null) {
      const dur = formatDuration(finishedAt - startedAt);
      return failed ? `Stopped after ${dur}` : `Done in ${dur}`;
    }
    return formatDuration(now - startedAt);
  })();

  return (
    <div className="space-y-5">
      <div className="flex justify-between items-baseline">
        <h3 className="text-xs font-bold uppercase tracking-widest text-ink-faint">Progress</h3>
        {elapsed && (
          <span
            className={`text-xs font-semibold tabular-nums ${
              failed ? 'text-error' : finishedAt !== null ? 'text-success' : 'text-ink-soft'
            }`}
          >
            {elapsed}
          </span>
        )}
      </div>

      <ProgressBar progress={overall} status={overallStatus} />

      <div className="space-y-4" role="list" aria-label="Processing steps">
        {steps.map(step => (
          <div key={step.id} className="space-y-2" role="listitem">
            <div className="flex justify-between items-center text-sm">
              <span className={`font-semibold flex items-center gap-2 ${STEP_LABEL_COLORS[step.status]}`}>
                <span
                  aria-hidden="true"
                  className={`text-base leading-none ${step.status === 'processing' ? 'animate-spin' : ''}`}
                >
                  {STEP_ICONS[step.status]}
                </span>
                {step.label}
              </span>
              <span className="text-ink-faint text-xs tabular-nums" aria-label={`${step.progress}%`}>
                {step.progress}%
              </span>
            </div>
            <ProgressBar progress={step.progress} status={step.status} thin />
          </div>
        ))}
      </div>
    </div>
  );
};

export default StepRail;

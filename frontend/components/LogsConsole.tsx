import React, { useEffect, useRef, useState } from 'react';

interface LogsConsoleProps {
  logs: string[];
  ariaLabel?: string;
}

const LogsConsole: React.FC<LogsConsoleProps> = ({ logs, ariaLabel = 'Processing logs' }) => {
  const [autoScroll, setAutoScroll] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const handleScroll = () => {
    if (containerRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
      const isAtBottom = Math.abs(scrollHeight - scrollTop - clientHeight) < 10;
      if (!isAtBottom && autoScroll) setAutoScroll(false);
      else if (isAtBottom && !autoScroll) setAutoScroll(true);
    }
  };

  return (
    <div className="bg-raised border border-edge rounded-2xl overflow-hidden">
      <div className="flex justify-between items-center px-6 pt-5 pb-3">
        <h3 className="text-xs font-bold uppercase tracking-widest text-ink-faint">Live Logs</h3>
        {!autoScroll && (
          <button
            onClick={() => setAutoScroll(true)}
            className="px-3 py-1 text-xs font-bold bg-brand-soft text-brand rounded-lg hover:brightness-95 dark:hover:brightness-110 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand rounded-lg"
          >
            Resume auto-scroll
          </button>
        )}
      </div>
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className={`font-mono text-[11px] leading-relaxed text-ink-soft px-6 pb-5 space-y-1 overflow-y-auto max-h-[320px]`}
        aria-label={ariaLabel}
        role="log"
        aria-live="off"
      >
        {logs.length > 0 ? (
          logs.map((log, i) => <p key={i}>{log}</p>)
        ) : (
          <p className="italic opacity-50">Waiting for process logs…</p>
        )}
      </div>
    </div>
  );
};

export default LogsConsole;

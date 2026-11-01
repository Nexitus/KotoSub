import React, { useEffect, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardAction, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

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
    <Card className="gap-3 py-5">
      <CardHeader className="px-5">
        <CardTitle className="text-sm">Live Logs</CardTitle>
        {!autoScroll && (
          <CardAction>
            <Button size="sm" variant="secondary" className="h-7 text-xs" onClick={() => setAutoScroll(true)}>
              Resume auto-scroll
            </Button>
          </CardAction>
        )}
      </CardHeader>
      <CardContent className="px-5">
        <div
          ref={containerRef}
          onScroll={handleScroll}
          className="font-mono text-[11px] leading-relaxed text-muted-foreground space-y-1 overflow-y-auto max-h-[320px]"
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
      </CardContent>
    </Card>
  );
};

export default LogsConsole;

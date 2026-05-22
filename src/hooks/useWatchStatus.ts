import { useEffect, useRef, useState, useCallback } from 'react';
import { isWatching, onWatchEvent } from '../api/ipc';
import type { WatchEvent } from '../api/types';

export interface WatchStatus {
  running: boolean;
  intervalSeconds?: number;
  lastEvent?: WatchEvent;
  lastError?: string;
}

export function useWatchStatus() {
  const [status, setStatus] = useState<WatchStatus>({ running: false });
  const unlistenRef = useRef<(() => void) | null>(null);

  const refresh = useCallback(async () => {
    try {
      const r = await isWatching();
      setStatus((s) => ({ ...s, running: r }));
    } catch (_) {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    void refresh();

    onWatchEvent((evt) => {
      if (cancelled) return;
      setStatus((s) => {
        const next: WatchStatus = { ...s, lastEvent: evt };
        switch (evt.type) {
          case 'started':
            next.running = true;
            next.intervalSeconds = evt.interval_seconds;
            next.lastError = undefined;
            break;
          case 'stopped':
            next.running = false;
            break;
          case 'failed':
            next.lastError = evt.message;
            break;
          default:
            break;
        }
        return next;
      });
    }).then((un) => {
      if (cancelled) {
        un();
      } else {
        unlistenRef.current = un;
      }
    });

    const t = window.setInterval(() => void refresh(), 5000);

    return () => {
      cancelled = true;
      window.clearInterval(t);
      if (unlistenRef.current) unlistenRef.current();
    };
  }, [refresh]);

  return { status, refresh };
}

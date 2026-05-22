import { useEffect, useState, useCallback } from 'react';
import type { Config } from '../api/types';
import { loadConfig, saveConfig } from '../api/ipc';

export function useConfig() {
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const cfg = await loadConfig();
      setConfig(cfg);
    } catch (e: any) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const save = useCallback(async (cfg: Config) => {
    setSaving(true);
    setError(null);
    try {
      await saveConfig(cfg);
      setConfig(cfg);
    } catch (e: any) {
      setError(String(e));
      throw e;
    } finally {
      setSaving(false);
    }
  }, []);

  return { config, setConfig, loading, saving, error, reload, save };
}

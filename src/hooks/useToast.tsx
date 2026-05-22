import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from 'react';
import { CheckCircle2, Info, X, AlertCircle } from 'lucide-react';

export type ToastKind = 'info' | 'success' | 'error';

export interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

interface ToastApi {
  show: (kind: ToastKind, message: string) => void;
  info: (msg: string) => void;
  success: (msg: string) => void;
  error: (msg: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

let idSeed = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const remove = useCallback((id: number) => {
    setToasts((arr) => arr.filter((t) => t.id !== id));
  }, []);

  const show = useCallback(
    (kind: ToastKind, message: string) => {
      const id = idSeed++;
      setToasts((arr) => [...arr, { id, kind, message }]);
      window.setTimeout(() => remove(id), 4000);
    },
    [remove]
  );

  const api: ToastApi = {
    show,
    info: (m) => show('info', m),
    success: (m) => show('success', m),
    error: (m) => show('error', m),
  };

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-stack">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`}>
            <span className="mt-0.5">
              {t.kind === 'success' && (
                <CheckCircle2 size={16} className="text-emerald-500" />
              )}
              {t.kind === 'info' && <Info size={16} className="text-primary" />}
              {t.kind === 'error' && (
                <AlertCircle size={16} className="text-red-500" />
              )}
            </span>
            <span className="flex-1 break-words">{t.message}</span>
            <button
              className="text-muted hover:text-ink"
              onClick={() => remove(t.id)}
              aria-label="关闭"
            >
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}

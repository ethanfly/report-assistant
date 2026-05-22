import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from 'react';
import { CheckCircle2, Info, X, AlertCircle, AlertTriangle } from 'lucide-react';

export type ToastKind = 'info' | 'success' | 'error';

export interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

export type AlertKind = 'info' | 'success' | 'error' | 'warning';

export interface AlertOptions {
  title?: string;
  kind?: AlertKind;
  /** 关闭按钮文案，默认 "我知道了" */
  okLabel?: string;
}

interface AlertEntry extends AlertOptions {
  id: number;
  message: string;
}

interface ToastApi {
  show: (kind: ToastKind, message: string) => void;
  info: (msg: string) => void;
  success: (msg: string) => void;
  error: (msg: string) => void;
  /** 持久弹框：必须用户点关闭才消失。多次调用会排队展示。 */
  alert: (message: string, opts?: AlertOptions) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

let idSeed = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [alerts, setAlerts] = useState<AlertEntry[]>([]);

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

  const closeAlert = useCallback((id: number) => {
    setAlerts((arr) => arr.filter((a) => a.id !== id));
  }, []);

  const alertFn = useCallback((message: string, opts?: AlertOptions) => {
    const id = idSeed++;
    setAlerts((arr) => [
      ...arr,
      { id, message, kind: opts?.kind ?? 'error', title: opts?.title, okLabel: opts?.okLabel },
    ]);
  }, []);

  const api: ToastApi = {
    show,
    info: (m) => show('info', m),
    success: (m) => show('success', m),
    error: (m) => show('error', m),
    alert: alertFn,
  };

  // 当前展示的 alert（FIFO）：只渲染最早的一条，关闭后才显示下一条，避免叠多个遮罩
  const current = alerts[0] ?? null;

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

      {current && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          // 点遮罩不关闭：用户必须明确点按钮，避免误触
        >
          <div
            role="alertdialog"
            aria-modal="true"
            className="max-w-md w-[90%] bg-card border border-border rounded-lg shadow-lg p-5"
          >
            <div className="flex items-start gap-3">
              <span className="mt-0.5 shrink-0">
                {current.kind === 'success' && (
                  <CheckCircle2 size={20} className="text-emerald-500" />
                )}
                {current.kind === 'info' && (
                  <Info size={20} className="text-primary" />
                )}
                {current.kind === 'warning' && (
                  <AlertTriangle size={20} className="text-amber-500" />
                )}
                {(current.kind === 'error' || !current.kind) && (
                  <AlertCircle size={20} className="text-red-500" />
                )}
              </span>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-ink mb-1">
                  {current.title ??
                    (current.kind === 'error'
                      ? '出错了'
                      : current.kind === 'warning'
                      ? '提示'
                      : '通知')}
                </div>
                <div className="text-sm text-ink2 whitespace-pre-wrap break-words max-h-[60vh] overflow-y-auto">
                  {current.message}
                </div>
              </div>
            </div>
            <div className="mt-4 flex justify-end">
              <button
                type="button"
                className="btn-primary h-8 px-4 text-sm"
                onClick={() => closeAlert(current.id)}
                autoFocus
              >
                {current.okLabel ?? '我知道了'}
              </button>
            </div>
          </div>
        </div>
      )}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}

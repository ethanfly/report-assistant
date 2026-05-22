import { useEffect, useMemo, useRef, useState } from 'react';
import dayjs, { type Dayjs } from 'dayjs';
import { Calendar, ChevronLeft, ChevronRight } from 'lucide-react';
import clsx from 'clsx';

interface DatePickerProps {
  value: string; // YYYY-MM-DD
  onChange: (v: string) => void;
  placeholder?: string;
  className?: string;
  hint?: string;
  label?: string;
  disabled?: boolean;
}

const WEEK_LABELS = ['日', '一', '二', '三', '四', '五', '六'];

/**
 * 紧凑像素风日历选择器：
 * - 输入框点击弹出 popover（缩放进入）
 * - 月份导航 ← 2025 年 1 月 →
 * - 7 列 × 6 行日期网格，今日高亮、选中实色
 * - 点击外部 / 选中后自动关闭
 */
export default function DatePicker({
  value,
  onChange,
  placeholder = '选择日期',
  className,
  hint,
  label,
  disabled,
}: DatePickerProps) {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<Dayjs>(() =>
    value ? dayjs(value) : dayjs()
  );
  const wrapRef = useRef<HTMLDivElement>(null);

  // 当外部 value 变化时同步视图
  useEffect(() => {
    if (value) setView(dayjs(value));
  }, [value]);

  // 点外部关闭
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (
        wrapRef.current &&
        !wrapRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  // 6×7 网格
  const days = useMemo(() => {
    const start = view.startOf('month').startOf('week');
    return Array.from({ length: 42 }, (_, i) => start.add(i, 'day'));
  }, [view]);

  const today = dayjs().format('YYYY-MM-DD');
  const selected = value || '';

  const pickDate = (d: Dayjs) => {
    onChange(d.format('YYYY-MM-DD'));
    setOpen(false);
  };

  return (
    <div className={clsx('w-full', className)}>
      {label && <label className="label">{label}</label>}
      <div className="relative" ref={wrapRef}>
        <input
          readOnly
          disabled={disabled}
          value={value}
          placeholder={placeholder}
          onClick={() => !disabled && setOpen((o) => !o)}
          className="input-base pl-9 cursor-pointer"
        />
        <Calendar
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-ink2 pointer-events-none"
        />

        {open && (
          <div className="absolute z-30 mt-1 left-0 w-[260px] bg-white border border-border rounded-card shadow-soft p-2 animate-pop">
            {/* 月份导航 */}
            <div className="flex items-center justify-between px-1 py-1">
              <button
                type="button"
                onClick={() => setView(view.subtract(1, 'month'))}
                className="w-6 h-6 flex items-center justify-center rounded-pix text-ink2 hover:bg-primary-50 hover:text-primary-700 transition-colors"
                title="上一月"
              >
                <ChevronLeft size={14} />
              </button>
              <div className="text-sm font-semibold text-ink select-none">
                {view.year()} 年 {view.month() + 1} 月
              </div>
              <button
                type="button"
                onClick={() => setView(view.add(1, 'month'))}
                className="w-6 h-6 flex items-center justify-center rounded-pix text-ink2 hover:bg-primary-50 hover:text-primary-700 transition-colors"
                title="下一月"
              >
                <ChevronRight size={14} />
              </button>
            </div>

            {/* 星期表头 */}
            <div className="grid grid-cols-7 mt-1 mb-1">
              {WEEK_LABELS.map((w) => (
                <div
                  key={w}
                  className="text-[11px] text-ink2 text-center py-1"
                >
                  {w}
                </div>
              ))}
            </div>

            {/* 日期网格 */}
            <div className="grid grid-cols-7 gap-[2px]">
              {days.map((d) => {
                const ds = d.format('YYYY-MM-DD');
                const otherMonth = d.month() !== view.month();
                const isToday = ds === today;
                const isSelected = ds === selected;
                return (
                  <button
                    key={ds}
                    type="button"
                    onClick={() => pickDate(d)}
                    className={clsx(
                      'h-7 text-[12px] rounded-pix flex items-center justify-center transition-all',
                      isSelected
                        ? 'bg-primary text-white font-semibold shadow-pix'
                        : isToday
                        ? 'bg-primary-50 text-primary-700 font-semibold'
                        : otherMonth
                        ? 'text-ink2/40 hover:bg-bg'
                        : 'text-ink hover:bg-primary-50'
                    )}
                  >
                    {d.date()}
                  </button>
                );
              })}
            </div>

            {/* 底部快捷 */}
            <div className="flex justify-between items-center mt-2 pt-2 border-t border-border">
              <button
                type="button"
                onClick={() => {
                  const t = dayjs();
                  setView(t);
                  onChange(t.format('YYYY-MM-DD'));
                  setOpen(false);
                }}
                className="text-[12px] text-primary-700 hover:underline"
              >
                今天
              </button>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="text-[12px] text-ink2 hover:text-ink"
              >
                关闭
              </button>
            </div>
          </div>
        )}
      </div>
      {hint && <p className="hint">{hint}</p>}
    </div>
  );
}

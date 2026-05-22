import { useEffect, useMemo, useRef, useState } from 'react';
import dayjs from 'dayjs';
import { Calendar, ChevronLeft, ChevronRight } from 'lucide-react';
import clsx from 'clsx';

interface MonthPickerProps {
  /** YYYY-MM-DD：所选月份的 1 号 */
  value: string;
  onChange: (firstOfMonthIso: string) => void;
  className?: string;
  hint?: string;
  label?: string;
  disabled?: boolean;
  placeholder?: string;
}

const MONTH_LABELS = [
  '1 月', '2 月', '3 月', '4 月', '5 月', '6 月',
  '7 月', '8 月', '9 月', '10 月', '11 月', '12 月',
];

/**
 * 像素风月份选择器
 * - 与 DatePicker 同款 popover 视觉
 * - 4×3 月份网格 + 年份切换
 * - 输入框显示 YYYY-MM；存储该月 1 号 ISO
 */
export default function MonthPicker({
  value,
  onChange,
  className,
  hint,
  label,
  disabled,
  placeholder = '选择月',
}: MonthPickerProps) {
  const [open, setOpen] = useState(false);
  const initial = value ? dayjs(value) : dayjs();
  const [year, setYear] = useState<number>(initial.year());
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (value) setYear(dayjs(value).year());
  }, [value]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  const display = useMemo(() => (value ? dayjs(value).format('YYYY-MM') : ''), [value]);
  const selected = value ? dayjs(value) : null;
  const now = dayjs();

  const pickMonth = (m: number) => {
    const v = dayjs(`${year}-${String(m + 1).padStart(2, '0')}-01`);
    onChange(v.format('YYYY-MM-DD'));
    setOpen(false);
  };

  return (
    <div className={clsx('w-full', className)}>
      {label && <label className="label">{label}</label>}
      <div className="relative" ref={wrapRef}>
        <input
          readOnly
          disabled={disabled}
          value={display}
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
            {/* 年份导航 */}
            <div className="flex items-center justify-between px-1 py-1">
              <button
                type="button"
                onClick={() => setYear((y) => y - 1)}
                className="w-6 h-6 flex items-center justify-center rounded-pix text-ink2 hover:bg-primary-50 hover:text-primary-700 transition-colors"
                title="上一年"
              >
                <ChevronLeft size={14} />
              </button>
              <div className="text-sm font-semibold text-ink select-none">
                {year} 年
              </div>
              <button
                type="button"
                onClick={() => setYear((y) => y + 1)}
                className="w-6 h-6 flex items-center justify-center rounded-pix text-ink2 hover:bg-primary-50 hover:text-primary-700 transition-colors"
                title="下一年"
              >
                <ChevronRight size={14} />
              </button>
            </div>

            {/* 4×3 月份网格 */}
            <div className="grid grid-cols-3 gap-[6px] mt-1">
              {MONTH_LABELS.map((m, idx) => {
                const isSelected =
                  !!selected && selected.year() === year && selected.month() === idx;
                const isCurrent = now.year() === year && now.month() === idx;
                return (
                  <button
                    key={m}
                    type="button"
                    onClick={() => pickMonth(idx)}
                    className={clsx(
                      'h-9 text-[13px] rounded-pix flex items-center justify-center transition-all',
                      isSelected
                        ? 'bg-primary text-white font-semibold shadow-pix'
                        : isCurrent
                        ? 'bg-primary-50 text-primary-700 font-semibold'
                        : 'text-ink hover:bg-primary-50'
                    )}
                  >
                    {m}
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
                  setYear(t.year());
                  onChange(t.startOf('month').format('YYYY-MM-DD'));
                  setOpen(false);
                }}
                className="text-[12px] text-primary-700 hover:underline"
              >
                本月
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

import { useEffect, useMemo, useRef, useState } from 'react';
import dayjs, { type Dayjs } from 'dayjs';
import isoWeek from 'dayjs/plugin/isoWeek';
import { Calendar, ChevronLeft, ChevronRight } from 'lucide-react';
import clsx from 'clsx';

dayjs.extend(isoWeek);

interface WeekPickerProps {
  /** ISO 周对应的周一日期，YYYY-MM-DD */
  value: string;
  onChange: (mondayIso: string) => void;
  className?: string;
  hint?: string;
  label?: string;
  disabled?: boolean;
  placeholder?: string;
}

const WEEK_LABELS = ['一', '二', '三', '四', '五', '六', '日'];

/**
 * 像素风周选择器
 * - 与 DatePicker 同款 popover 视觉
 * - 整行（一周）作为一个选项：悬停整行高亮，点击选中整周
 * - value 存储该周的周一日期（ISO）
 * - 显示形如：2025 第 03 周 · 1/13 - 1/19
 */
export default function WeekPicker({
  value,
  onChange,
  className,
  hint,
  label,
  disabled,
  placeholder = '选择周',
}: WeekPickerProps) {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<Dayjs>(() =>
    value ? dayjs(value) : dayjs()
  );
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (value) setView(dayjs(value));
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

  // 6 行 × 7 列；以 ISO 周（周一）为起点
  const rows = useMemo(() => {
    const start = view.startOf('month').startOf('isoWeek');
    return Array.from({ length: 6 }, (_, r) =>
      Array.from({ length: 7 }, (_, c) => start.add(r * 7 + c, 'day'))
    );
  }, [view]);

  // 选中周的周一
  const selectedMonday = value ? dayjs(value).startOf('isoWeek') : null;

  const display = useMemo(() => {
    if (!value) return '';
    const m = dayjs(value);
    const start = m.startOf('isoWeek');
    const end = start.add(6, 'day');
    const weekNo = m.isoWeek();
    return `${m.isoWeekYear()} 第 ${String(weekNo).padStart(2, '0')} 周 · ${start.format('M/D')} - ${end.format('M/D')}`;
  }, [value]);

  const pickWeek = (anyDay: Dayjs) => {
    const monday = anyDay.startOf('isoWeek');
    onChange(monday.format('YYYY-MM-DD'));
    setOpen(false);
  };

  const todayStr = dayjs().format('YYYY-MM-DD');

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
          <div className="absolute z-30 mt-1 left-0 w-[300px] bg-white border border-border rounded-card shadow-soft p-2 animate-pop">
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

            {/* 表头：周号 + 周一..周日 */}
            <div className="grid grid-cols-[36px_repeat(7,1fr)] mt-1 mb-1">
              <div className="text-[11px] text-ink2 text-center py-1">周</div>
              {WEEK_LABELS.map((w) => (
                <div
                  key={w}
                  className="text-[11px] text-ink2 text-center py-1"
                >
                  {w}
                </div>
              ))}
            </div>

            {/* 周行 */}
            <div className="space-y-[2px]">
              {rows.map((days, ri) => {
                const monday = days[0];
                const weekNo = monday.isoWeek();
                const isSelected =
                  !!selectedMonday &&
                  monday.format('YYYY-MM-DD') ===
                    selectedMonday.format('YYYY-MM-DD');
                return (
                  <button
                    key={ri}
                    type="button"
                    onClick={() => pickWeek(monday)}
                    className={clsx(
                      'w-full grid grid-cols-[36px_repeat(7,1fr)] rounded-pix transition-all',
                      isSelected
                        ? 'bg-primary text-white shadow-pix'
                        : 'hover:bg-primary-50'
                    )}
                  >
                    <div
                      className={clsx(
                        'h-7 text-[11px] flex items-center justify-center font-mono',
                        isSelected ? 'text-white/90' : 'text-ink2'
                      )}
                    >
                      {String(weekNo).padStart(2, '0')}
                    </div>
                    {days.map((d) => {
                      const ds = d.format('YYYY-MM-DD');
                      const otherMonth = d.month() !== view.month();
                      const isToday = ds === todayStr;
                      return (
                        <div
                          key={ds}
                          className={clsx(
                            'h-7 text-[12px] flex items-center justify-center transition-colors',
                            isSelected
                              ? 'text-white font-semibold'
                              : isToday
                              ? 'text-primary-700 font-semibold'
                              : otherMonth
                              ? 'text-ink2/40'
                              : 'text-ink'
                          )}
                        >
                          {d.date()}
                        </div>
                      );
                    })}
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
                  onChange(t.startOf('isoWeek').format('YYYY-MM-DD'));
                  setOpen(false);
                }}
                className="text-[12px] text-primary-700 hover:underline"
              >
                本周
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

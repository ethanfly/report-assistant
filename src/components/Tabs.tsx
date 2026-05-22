import { useEffect, useRef, useState, type ReactNode } from 'react';
import clsx from 'clsx';

export interface TabItem<T extends string = string> {
  key: T;
  label: ReactNode;
  icon?: ReactNode;
}

interface TabsProps<T extends string = string> {
  tabs: TabItem<T>[];
  value: T;
  onChange: (key: T) => void;
  className?: string;
}

/**
 * 通用 Tabs：横排，下方 2px primary 下划线，切换时滑动
 * 用法：<Tabs tabs={[{ key, label }]} value={tab} onChange={setTab} />
 */
export default function Tabs<T extends string = string>({
  tabs,
  value,
  onChange,
  className,
}: TabsProps<T>) {
  const containerRef = useRef<HTMLDivElement>(null);
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  const [bar, setBar] = useState<{ left: number; width: number }>({
    left: 0,
    width: 0,
  });

  // 同步下划线位置
  useEffect(() => {
    const el = tabRefs.current[value];
    const wrap = containerRef.current;
    if (el && wrap) {
      const elRect = el.getBoundingClientRect();
      const wrapRect = wrap.getBoundingClientRect();
      setBar({
        left: elRect.left - wrapRect.left,
        width: elRect.width,
      });
    }
  }, [value, tabs.length]);

  return (
    <div
      ref={containerRef}
      className={clsx(
        'relative flex items-end gap-1 border-b border-border',
        className
      )}
    >
      {tabs.map((t) => {
        const active = t.key === value;
        return (
          <button
            key={t.key}
            ref={(el) => {
              tabRefs.current[t.key] = el;
            }}
            onClick={() => onChange(t.key)}
            className={clsx(
              'relative px-4 py-2 text-sm font-medium transition-all duration-200',
              'flex items-center gap-1.5 rounded-t-pix',
              active
                ? 'text-primary-700'
                : 'text-ink2 hover:text-ink hover:bg-primary-50/50'
            )}
          >
            {t.icon}
            <span>{t.label}</span>
          </button>
        );
      })}
      {/* 滑动下划线 */}
      <span
        className="absolute bottom-0 h-[2px] bg-primary rounded-t-pix transition-all duration-300 ease-out"
        style={{ left: bar.left, width: bar.width }}
      />
    </div>
  );
}

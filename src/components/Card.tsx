import { type ReactNode } from 'react';
import clsx from 'clsx';

interface CardProps {
  children: ReactNode;
  className?: string;
  title?: ReactNode;
  description?: ReactNode;
  footer?: ReactNode;
  noPadding?: boolean;
  /** 是否启用 hover 微抬效果（默认 true） */
  hoverable?: boolean;
}

/**
 * 像素风卡片：1px 边框 + 像素风圆角 + hover 微抬
 */
export default function Card({
  children,
  className,
  title,
  description,
  footer,
  noPadding,
  hoverable = true,
}: CardProps) {
  return (
    <section
      className={clsx(
        'bg-card rounded-card border border-border shadow-card transition-all duration-200',
        hoverable && 'hover:-translate-y-px hover:shadow-soft',
        !noPadding && 'p-5',
        className
      )}
    >
      {(title || description) && (
        <header className={clsx('mb-4', noPadding && 'p-5 pb-0')}>
          {title && (
            <h3 className="text-[15px] font-semibold text-ink">{title}</h3>
          )}
          {description && (
            <p className="text-xs text-ink2 mt-1">{description}</p>
          )}
        </header>
      )}
      {children}
      {footer ? (
        <footer
          className={clsx(
            'mt-4 pt-3 border-t border-border',
            noPadding && 'p-5 pt-3'
          )}
        >
          {footer}
        </footer>
      ) : null}
    </section>
  );
}

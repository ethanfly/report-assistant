import { type ReactNode } from 'react';
import clsx from 'clsx';

interface CardProps {
  children: ReactNode;
  className?: string;
  title?: ReactNode;
  description?: ReactNode;
  footer?: ReactNode;
  noPadding?: boolean;
}

export default function Card({
  children,
  className,
  title,
  description,
  footer,
  noPadding,
}: CardProps) {
  return (
    <section
      className={clsx(
        'bg-white rounded-card shadow-card border border-border',
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
            <p className="text-xs text-muted mt-1">{description}</p>
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

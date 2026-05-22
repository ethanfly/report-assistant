import { type ButtonHTMLAttributes, forwardRef, type ReactNode } from 'react';
import clsx from 'clsx';
import Spinner from './Spinner';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
// 全局只保留 sm / md 两档
type Size = 'sm' | 'md';

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}

const variantClass: Record<Variant, string> = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  ghost: 'btn-ghost',
  danger: 'btn-danger',
};

// 强制等高，sm/md 二选一；同一行使用同一档可保证视觉对齐
const sizeClass: Record<Size, string> = {
  sm: 'h-8 px-3 text-xs',
  md: 'h-9 px-4 text-sm',
};

const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = 'primary', size = 'md', loading, icon, className, children, disabled, ...rest },
  ref
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={clsx(variantClass[variant], sizeClass[size], className)}
      {...rest}
    >
      {loading ? (
        <Spinner size={3} />
      ) : icon ? (
        <span className="shrink-0 inline-flex items-center">{icon}</span>
      ) : null}
      {children}
    </button>
  );
});

export default Button;

import { type InputHTMLAttributes, type TextareaHTMLAttributes, type SelectHTMLAttributes, forwardRef } from 'react';
import clsx from 'clsx';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, className, id, ...rest },
  ref
) {
  return (
    <div className="w-full">
      {label && (
        <label htmlFor={id} className="label">
          {label}
        </label>
      )}
      <input
        id={id}
        ref={ref}
        className={clsx('input-base', error && 'border-red-400 focus:border-red-500', className)}
        {...rest}
      />
      {hint && !error && <p className="hint">{hint}</p>}
      {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
    </div>
  );
});

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  hint?: string;
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, hint, error, className, id, rows, ...rest },
  ref
) {
  return (
    <div className="w-full">
      {label && (
        <label htmlFor={id} className="label">
          {label}
        </label>
      )}
      <textarea
        id={id}
        ref={ref}
        rows={rows ?? 4}
        className={clsx('input-base resize-y', error && 'border-red-400', className)}
        {...rest}
      />
      {hint && !error && <p className="hint">{hint}</p>}
      {error && <p className="text-xs text-red-500 mt-1">{error}</p>}
    </div>
  );
});

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  hint?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, hint, children, id, className, ...rest },
  ref
) {
  return (
    <div className="w-full">
      {label && (
        <label htmlFor={id} className="label">
          {label}
        </label>
      )}
      <select id={id} ref={ref} className={clsx('input-base', className)} {...rest}>
        {children}
      </select>
      {hint && <p className="hint">{hint}</p>}
    </div>
  );
});

export default Input;

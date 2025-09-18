'use client';
import clsx from 'clsx';
export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={clsx(
        'bg-[var(--surface-soft)] border border-[var(--border)]/60 rounded-lg px-3.5 py-2.5 h-12 text-sm text-[var(--text)] placeholder:text-[var(--muted)] shadow-[var(--shadow-sm)]',
        'focus:outline-none focus:ring-2 focus:ring-[var(--ring)] focus:border-[var(--accent)] transition-colors duration-150 backdrop-blur-md',
        props.className
      )}
    />
  );
}

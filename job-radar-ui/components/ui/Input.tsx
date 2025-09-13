'use client';
import clsx from 'clsx';
export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={clsx(
        'bg-[var(--surface)] border border-[var(--border)] rounded-md px-3 py-2 text-sm',
        'focus:outline-none focus:ring-2 focus:ring-[var(--ring)] focus:border-[var(--accent)]',
        props.className
      )}
    />
  );
}

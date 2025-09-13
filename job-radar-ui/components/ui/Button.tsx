'use client';
import clsx from 'clsx';

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'ghost' | 'link';
};
export function Button({ variant = 'primary', className, ...rest }: Props) {
  const base =
    'inline-flex items-center justify-center rounded-md text-sm font-semibold transition px-3 py-2';
  const style = {
    primary: 'bg-[var(--accent)] text-[#06141f] hover:brightness-105',
    ghost:
      'border border-[var(--border)] text-[var(--text)] hover:border-[var(--accent)] hover:text-[var(--accent)] bg-transparent',
    link: 'text-[var(--accent)] underline px-0 py-0'
  }[variant];
  return <button className={clsx(base, style, className)} {...rest} />;
}

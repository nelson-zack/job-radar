'use client';
import clsx from 'clsx';

type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'ghost' | 'link';
};
export function Button({ variant = 'primary', className, ...rest }: Props) {
  const base =
    'inline-flex h-12 items-center justify-center rounded-lg text-sm font-semibold tracking-tight transition px-3.5 py-2.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]/40 focus-visible:ring-offset-0';
  const style = {
    primary:
      'bg-gradient-to-tr from-[var(--accent)] to-[var(--accent-2)] text-[#04131f] shadow-[var(--shadow-sm)] hover:shadow-[var(--shadow-lg)] hover:brightness-[1.05]',
    ghost:
      'border border-[var(--border)]/70 text-[var(--text)] bg-transparent hover:border-[var(--accent)] hover:text-[var(--accent)]',
    link: 'text-[var(--accent)] underline px-0 py-0 hover:text-[var(--accent-2)]'
  }[variant];
  return <button className={clsx(base, style, className)} {...rest} />;
}

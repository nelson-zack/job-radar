import clsx from 'clsx';
import type { PropsWithChildren } from 'react';

type Variant = 'accent' | 'neutral' | 'warning' | 'muted';

type Props = PropsWithChildren<{
  variant?: Variant;
  className?: string;
}>;

export function Badge({ variant = 'neutral', className, children }: Props) {
  const base =
    'inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[0.68rem] font-semibold uppercase tracking-[0.12em]';
  const tone = {
    accent: 'border border-transparent bg-[var(--accent-soft)] text-[var(--tag-text)]',
    neutral:
      'border border-[var(--border)]/60 bg-transparent text-[color-mix(in srgb,var(--text) 88%, transparent 12%)]',
    warning: 'border border-[#f59e0b]/35 bg-[#f59e0b]/15 text-[#fbd38d]',
    muted: 'border border-transparent bg-transparent text-[var(--muted)]'
  }[variant];

  return <span className={clsx(base, tone, className)}>{children}</span>;
}

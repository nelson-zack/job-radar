// components/layout/PageShell.tsx

import React from 'react';

type Props = { children: React.ReactNode };

export default function PageShell({ children }: Props) {
  return (
    <div className='relative min-h-screen overflow-hidden bg-[var(--bg)] text-[var(--text)]'>
      <div className='pointer-events-none absolute inset-0 -z-10 opacity-95'>
        <div className='absolute inset-0 bg-[radial-gradient(circle_at_top,var(--accent-soft)0%,transparent55%)]' />
        <div className='absolute inset-0 bg-[radial-gradient(circle_at_bottom_right,rgba(8,25,48,0.6)0%,transparent65%)]' />
        <div className='absolute inset-0 bg-[radial-gradient(circle_at_bottom_left,rgba(32,54,94,0.35)0%,transparent60%)]' />
      </div>
      <div className='relative mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 lg:px-10'>
        {children}
      </div>
    </div>
  );
}

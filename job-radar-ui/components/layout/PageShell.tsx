// components/layout/PageShell.tsx

import React from 'react';

type Props = React.PropsWithChildren<{}>;

export default function PageShell({ children }: Props) {
  return (
    <div className='min-h-screen bg-[var(--bg)] text-[var(--text)]'>
      <div className='mx-auto max-w-6xl px-4 sm:px-6 lg:px-8 py-6'>
        {children}
      </div>
    </div>
  );
}

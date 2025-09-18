// app/admin/page.tsx
'use client';

import { useState } from 'react';
import PageShell from '@/components/layout/PageShell';
import { IS_PUBLIC_READONLY } from '@/utils/env';

export default function AdminPage() {
  const [out, setOut] = useState<string>('');

  const readOnly = IS_PUBLIC_READONLY;

  const runCurated = async () => {
    if (readOnly) {
      setOut('Read-only mode enabled: write actions are disabled.');
      return;
    }
    setOut('Running /ingest/curated...');
    try {
      const r = await fetch('/api/ingest-curated', { method: 'POST' });
      const txt = await r.text();
      setOut(`${r.status}: ${txt}`);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : typeof err === 'string' ? err : 'unknown';
      setOut(`Error: ${message}`);
    }
  };

  return (
    <PageShell>
      <div className='max-w-4xl mx-auto p-6 space-y-4'>
        <h1 className='text-2xl font-bold'>Admin</h1>
        <button
          onClick={runCurated}
          className='rounded-md bg-white/10 px-4 py-2 transition disabled:opacity-40 disabled:cursor-not-allowed'
          disabled={readOnly}
        >
          Ingest curated (GitHub lists)
        </button>
        {readOnly && (
          <p className='text-sm text-[var(--muted)]'>
            Public read-only mode is active. Enable writes by setting <code>PUBLIC_READONLY=false</code>.
          </p>
        )}
        <pre className='whitespace-pre-wrap text-sm opacity-80'>{out}</pre>
      </div>
    </PageShell>
  );
}

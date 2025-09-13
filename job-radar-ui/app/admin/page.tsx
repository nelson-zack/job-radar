// app/admin/page.tsx
'use client';

import { useState } from 'react';
import PageShell from '@/components/layout/PageShell';

export default function AdminPage() {
  const [out, setOut] = useState<string>('');

  const runCurated = async () => {
    setOut('Running /ingest/curated...');
    try {
      const r = await fetch('/api/ingest-curated', { method: 'POST' });
      const txt = await r.text();
      setOut(`${r.status}: ${txt}`);
    } catch (e: any) {
      setOut(`Error: ${e?.message ?? 'unknown'}`);
    }
  };

  return (
    <PageShell>
      <div className='max-w-4xl mx-auto p-6 space-y-4'>
        <h1 className='text-2xl font-bold'>Admin</h1>
        <button
          onClick={runCurated}
          className='rounded-md bg-white/10 px-4 py-2 hover:bg-white/20 transition'
        >
          Ingest curated (GitHub lists)
        </button>
        <pre className='whitespace-pre-wrap text-sm opacity-80'>{out}</pre>
      </div>
    </PageShell>
  );
}

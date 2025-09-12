'use client';

import { useEffect, useState } from 'react';
import { fetchJobs } from '@/lib/api';
import JobTable from '@/components/JobTable';

export default function Home() {
  const [level, setLevel] = useState<string>('');
  const [query, setQuery] = useState<string>(''); // skills_any
  const [jobs, setJobs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data = await fetchJobs({
        limit: 25,
        order: 'id_desc',
        level: level || undefined,
        skills_any: query || undefined
      });
      setJobs(data.items);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  return (
    <main className='max-w-5xl mx-auto p-6 space-y-4'>
      <h1 className='text-2xl font-semibold'>Job Radar</h1>

      <div className='flex flex-wrap gap-3 items-end'>
        <div>
          <label className='block text-xs font-medium mb-1'>Level</label>
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            className='border rounded px-2 py-1'
          >
            <option value=''>Any</option>
            <option value='junior'>Junior</option>
            <option value='mid'>Mid</option>
            <option value='senior'>Senior</option>
          </select>
        </div>

        <div>
          <label className='block text-xs font-medium mb-1'>Skills (any)</label>
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder='python, react, sql'
            className='border rounded px-2 py-1 w-64'
          />
        </div>

        <button
          onClick={load}
          disabled={loading}
          className='bg-black text-white rounded px-3 py-1 disabled:opacity-50'
        >
          {loading ? 'Loading…' : 'Search'}
        </button>
      </div>

      <JobTable jobs={jobs} />
    </main>
  );
}

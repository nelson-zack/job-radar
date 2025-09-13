// app/page.tsx
import JobTable from '@/components/JobTable';
import FiltersBar from '@/components/FiltersBar';
import Pagination from '@/components/Pagination';
import { fetchJobs } from '@/lib/api';
import type { JobsResponse } from '@/lib/types';
import PageShell from '@/components/layout/PageShell';

const PAGE_SIZE_DEFAULT = 25;

function toInt(v: string | string[] | undefined, d: number) {
  const n = Number(v);
  return Number.isFinite(n) && n >= 0 ? n : d;
}

export default async function Home({
  searchParams
}: {
  // In Next 15+, searchParams is a Promise in Server Components
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;

  const level = sp.level ?? 'any';
  const skills = sp.skills ?? '';
  const page = toInt(sp.page, 0);
  const limit = toInt(sp.limit, PAGE_SIZE_DEFAULT);
  const offset = page * limit;

  const data: JobsResponse = await fetchJobs({
    level: level === 'any' ? undefined : level,
    skills_any: skills,
    limit,
    offset,
    order: 'id_desc'
  });

  const totalPages = Math.max(1, Math.ceil((data.total ?? 0) / limit));

  const makeHref = (p: number) => {
    const params = new URLSearchParams({
      level,
      skills,
      page: String(p),
      limit: String(limit)
    });
    return `/?${params.toString()}`;
  };

  return (
    <PageShell>
      <h1 className='text-2xl font-bold'>Job Radar</h1>

      {/* Client component handles its own form submit/navigation */}
      <FiltersBar initialLevel={level} initialSkills={skills} />

      <JobTable jobs={data.items} />

      <Pagination page={page} totalPages={totalPages} makeHref={makeHref} />

      <p className='text-xs text-[var(--muted)]'>
        Showing {Math.min(limit, data.items.length)} of {data.total}
      </p>
    </PageShell>
  );
}

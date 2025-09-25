// app/page.tsx
import JobTable from '@/components/JobTable';
import FiltersBar from '@/components/FiltersBar';
import Pagination from '@/components/Pagination';
import { fetchJobs } from '@/lib/api';
import type { JobsResponse } from '@/lib/types';
import PageShell from '@/components/layout/PageShell';
import { ALLOWED_ORDERS_SET, Order } from '@/lib/sort';
import { getVisibleProviders } from '@/lib/providers';

const PAGE_SIZE_DEFAULT = 25;
const ENABLE_EXPERIMENTAL = (process.env.ENABLE_EXPERIMENTAL ?? 'false').toLowerCase() === 'true';

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
  const providerFilter = (sp.provider && sp.provider !== 'all') ? sp.provider : 'all';
  const rawOrder = sp.order ?? 'posted_at_desc';
  const order: Order = ALLOWED_ORDERS_SET.has(rawOrder as Order)
    ? (rawOrder as Order)
    : 'posted_at_desc';
  const page = toInt(sp.page, 0);
  const limit = toInt(sp.limit, PAGE_SIZE_DEFAULT);
  const offset = page * limit;

  // Only include filters if they are meaningful (avoid level=any, empty skills)
  let data: JobsResponse;
  let fetchError: string | null = null;

  try {
    data = await fetchJobs({
      ...(level !== 'any' ? { level } : {}),
      ...(skills ? { skills_any: skills } : {}),
      ...(providerFilter !== 'all' ? { provider: providerFilter } : {}),
      limit,
      offset,
      order
    });
  } catch (error) {
    console.error('Failed to load jobs from API', error);
    fetchError = 'Unable to load jobs right now. Please retry shortly.';
    data = {
      items: [],
      total: 0,
      limit,
      offset
    };
  }

  const providerOptions = getVisibleProviders(ENABLE_EXPERIMENTAL);

  const totalPages = Math.max(1, Math.ceil((data.total ?? 0) / limit));

  const makeHref = (p: number) => {
    const params = new URLSearchParams({
      order,
      page: String(p),
      limit: String(limit)
    });
    if (level !== 'any') params.set('level', level);
    if (skills) params.set('skills', skills);
    if (providerFilter !== 'all') params.set('provider', providerFilter);
    return `/?${params.toString()}`;
  };

  const activeChips: string[] = [];
  if (level !== 'any') activeChips.push(level);
  if (skills) activeChips.push(skills);
  if (providerFilter !== 'all') activeChips.push(`provider: ${providerFilter}`);

  return (
    <PageShell>
      <header className='mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between'>
        <div className='space-y-2'>
          <h1 className='text-3xl font-semibold text-[var(--text-strong)]'>Job Radar</h1>
          <p className='text-sm text-[var(--muted)]'>
            Surfacing remote-friendly early-career software roles pulled straight from ATS sources.
          </p>
        </div>
        <div className='flex flex-wrap items-center gap-2'>
          <span className='chip normal-case tracking-normal'>Total {data.total}</span>
          <span className='chip normal-case tracking-normal'>Page {page + 1}</span>
        </div>
      </header>

      <FiltersBar
        initialLevel={level}
        initialSkills={skills}
        initialOrder={order}
        initialProvider={providerFilter}
        providers={providerOptions}
      />

      {fetchError ? (
        <div className='mb-4 rounded-2xl border border-red-400/40 bg-red-500/10 p-4 text-sm font-medium text-red-200 shadow-[var(--shadow-sm)]'>
          {fetchError}
        </div>
      ) : null}

      {activeChips.length > 0 && (
        <div className='mb-4 flex flex-wrap items-center gap-2 text-xs'>
          <span className='uppercase tracking-[0.18em] text-[var(--muted)]'>Filters</span>
          {activeChips.map((c, i) => (
            <span key={i} className='chip normal-case tracking-normal'>
              {c}
            </span>
          ))}
        </div>
      )}

      <JobTable jobs={data.items} />

      <Pagination page={page} totalPages={totalPages} makeHref={makeHref} />

      <p className='mt-3 text-xs text-[var(--muted)]'>
        Showing {Math.min(limit, data.items.length)} of {data.total} roles
      </p>
    </PageShell>
  );
}

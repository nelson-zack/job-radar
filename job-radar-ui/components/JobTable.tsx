import type { Job } from '@/lib/types';
import { Badge } from './ui/Badge';

type Props = { jobs: Job[] };

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'] as const;

function normalizeLabel(value?: string | null) {
  if (!value) return '';
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '');
}

function shouldShowSlug(slug?: string | null, display?: string | null) {
  if (!slug) return false;
  const normalizedSlug = normalizeLabel(slug);
  const normalizedDisplay = normalizeLabel(display);
  if (!normalizedSlug) return false;
  return normalizedSlug !== normalizedDisplay;
}

function formatPosted(date: string | null | undefined) {
  if (!date) return '—';
  const iso = date.slice(0, 10);
  const [year, month, day] = iso.split('-');
  const monthIndex = Number(month) - 1;
  if (!year || monthIndex < 0 || monthIndex >= MONTHS.length || !day) return '—';
  return `${MONTHS[monthIndex]} ${String(Number(day))}, ${year}`;
}

function levelBadge(level?: string | null) {
  const normalized = (level ?? 'unknown').toLowerCase();
  if (normalized === 'senior') {
    return <Badge variant='warning'>Senior</Badge>;
  }
  if (normalized === 'mid') {
    return <Badge variant='neutral'>Mid</Badge>;
  }
  return <Badge variant='accent'>Junior</Badge>;
}

function JobCard({ job }: { job: Job }) {
  const companyDisplay = job.company_name || job.company;
  const posted = formatPosted(job.posted_at ?? null);

  return (
    <article className='rounded-2xl border border-[var(--border)]/50 bg-[var(--surface-3)]/70 p-4 shadow-[var(--shadow-md)] backdrop-blur-xl'>
      <header className='flex items-start justify-between gap-3'>
        <div className='space-y-1'>
          <h3 className='text-base font-semibold text-[var(--text-strong)]'>{companyDisplay}</h3>
          {shouldShowSlug(job.company, companyDisplay) ? (
            <p className='text-[0.65rem] uppercase tracking-[0.2em] text-[var(--muted)]'>
              {job.company}
            </p>
          ) : null}
        </div>
        <a
          className='link inline-flex items-center gap-1 text-sm'
          href={job.url}
          target='_blank'
          rel='noopener noreferrer'
        >
          Apply <span aria-hidden>→</span>
        </a>
      </header>

      <p className='mt-3 text-sm text-[color-mix(in srgb,var(--text) 90%, transparent 10%)]'>
        {job.title}
      </p>

      <dl className='mt-4 grid grid-cols-2 gap-3 text-xs text-[var(--muted)]'>
        <div className='flex flex-col items-center gap-1 text-center'>
          <dt className='uppercase tracking-[0.16em]'>Level</dt>
          <dd>{levelBadge(job.level)}</dd>
        </div>
        <div className='flex flex-col items-center gap-1 text-center'>
          <dt className='uppercase tracking-[0.16em]'>Remote</dt>
          <dd>{job.is_remote ? <Badge variant='accent'>Remote</Badge> : <Badge variant='muted'>Onsite</Badge>}</dd>
        </div>
        <div className='flex flex-col items-center gap-1 text-center'>
          <dt className='uppercase tracking-[0.16em]'>Posted</dt>
          <dd className='font-mono text-[0.7rem] uppercase tracking-[0.18em] text-[var(--muted)]'>{posted}</dd>
        </div>
        <div className='flex flex-col items-center gap-1 text-center'>
          <dt className='uppercase tracking-[0.16em]'>Link</dt>
          <dd>
            <a
              className='link inline-flex items-center gap-1 text-xs'
              href={job.url}
              target='_blank'
              rel='noopener noreferrer'
            >
              Open <span aria-hidden>↗</span>
            </a>
          </dd>
        </div>
      </dl>
    </article>
  );
}

export default function JobTable({ jobs }: Props) {
  if (!jobs.length)
    return (
      <div className='rounded-2xl border border-[var(--border)]/60 bg-[var(--surface-3)]/60 p-8 text-center text-sm text-[var(--muted)] shadow-[var(--shadow-md)]'>
        No results. Try relaxing your filters or expand the skill search.
      </div>
    );

  return (
    <div className='space-y-4'>
      <div className='space-y-3 md:hidden'>
        {jobs.map((job) => (
          <JobCard key={`card-${job.id}`} job={job} />
        ))}
      </div>

      <div className='hidden overflow-hidden rounded-2xl border border-[var(--border)]/60 bg-[var(--surface-3)]/60 shadow-[var(--shadow-lg)] backdrop-blur-xl md:block'>
        <div className='overflow-x-auto'>
          <table className='table-card w-full table-fixed text-left text-sm text-[var(--text)]'>
            <colgroup>
              <col className='w-[24%]' />
              <col className='w-[34%]' />
              <col className='w-[14%]' />
              <col className='w-[14%]' />
              <col className='w-[12%]' />
              <col className='w-[12%]' />
            </colgroup>
            <thead>
              <tr>
                <th className='th text-left'>Company</th>
                <th className='th text-left'>Title</th>
                <th className='th text-center'>Level</th>
                <th className='th text-center'>Remote</th>
                <th className='th text-right'>Posted</th>
                <th className='th text-right'>Action</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => {
                const companyDisplay = job.company_name || job.company;
                const posted = formatPosted(job.posted_at ?? null);
                const slug = shouldShowSlug(job.company, companyDisplay) ? job.company : null;

                return (
                  <tr key={job.id}>
                    <td className='td align-top sm:align-middle'>
                      <div className='flex flex-col gap-1'>
                        <span className='text-sm font-semibold text-[var(--text-strong)] sm:text-base'>
                          {companyDisplay}
                        </span>
                        {slug ? (
                          <span className='text-[0.65rem] uppercase tracking-[0.18em] text-[var(--muted)]'>
                            {slug}
                          </span>
                        ) : null}
                      </div>
                    </td>

                    <td className='td align-top sm:align-middle'>
                      <p className='clamp-2 break-words text-sm leading-6 text-[color-mix(in srgb,var(--text) 92%, transparent 8%)] sm:text-[0.95rem]'>
                        {job.title}
                      </p>
                    </td>

                    <td className='td align-top text-center sm:align-middle'>{levelBadge(job.level)}</td>

                    <td className='td align-top text-center sm:align-middle'>
                      {job.is_remote ? (
                        <Badge variant='accent'>Remote</Badge>
                      ) : (
                        <Badge variant='muted'>Onsite</Badge>
                      )}
                    </td>

                    <td className='td align-top text-right font-mono text-xs uppercase tracking-[0.18em] text-[var(--muted)] sm:align-middle sm:text-sm'>
                      {posted}
                    </td>

                    <td className='td align-top text-right sm:align-middle'>
                      <a
                        className='link inline-flex items-center gap-1 text-sm'
                        href={job.url}
                        target='_blank'
                        rel='noopener noreferrer'
                      >
                        Apply <span aria-hidden>→</span>
                      </a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

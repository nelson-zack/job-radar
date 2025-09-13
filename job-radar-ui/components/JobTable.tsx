import type { Job } from '@/lib/types';

type Props = { jobs: Job[] };

export default function JobTable({ jobs }: Props) {
  if (!jobs.length)
    return <p className='text-sm text-[var(--muted)]'>No results.</p>;

  return (
    <div className='overflow-x-auto'>
      <table className='table-card text-sm text-left'>
        <thead>
          <tr>
            <th className='th'>Company</th>
            <th className='th'>Title</th>
            <th className='th'>Level</th>
            <th className='th'>Remote</th>
            <th className='th'>Posted</th>
            <th className='th'></th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((j, i) => (
            <tr
              key={j.id}
              className='hover:bg-[var(--surface-2)] transition-colors'
            >
              <td className='td whitespace-nowrap'>
                {j.company_name || j.company}
              </td>
              <td className='td whitespace-nowrap'>{j.title}</td>
              <td className='td whitespace-nowrap'>{j.level ?? '—'}</td>
              <td className='td whitespace-nowrap'>
                {j.is_remote ? '✅' : '—'}
              </td>
              <td className='td whitespace-nowrap'>
                {j.posted_at ? new Date(j.posted_at).toLocaleDateString() : '—'}
              </td>
              <td className='td whitespace-nowrap'>
                <a
                  className='link'
                  href={j.url}
                  target='_blank'
                  rel='noopener noreferrer'
                >
                  Apply
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

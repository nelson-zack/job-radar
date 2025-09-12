import type { Job } from '@/lib/api';

export default function JobTable({ jobs }: { jobs: Job[] }) {
  if (!jobs.length) return <p className='text-sm text-gray-500'>No results.</p>;

  return (
    <div className='overflow-x-auto'>
      <table className='min-w-full text-sm'>
        <thead>
          <tr className='text-left border-b'>
            <th className='p-2'>Company</th>
            <th className='p-2'>Title</th>
            <th className='p-2'>Level</th>
            <th className='p-2'>Remote</th>
            <th className='p-2'>Posted</th>
            <th className='p-2'></th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((j) => (
            <tr key={j.id} className='border-b hover:bg-gray-50'>
              <td className='p-2'>{j.company_name || j.company}</td>
              <td className='p-2'>{j.title}</td>
              <td className='p-2'>{j.level ?? '—'}</td>
              <td className='p-2'>{j.is_remote ? '✅' : '—'}</td>
              <td className='p-2'>
                {j.posted_at ? new Date(j.posted_at).toLocaleDateString() : '—'}
              </td>
              <td className='p-2'>
                <a
                  href={j.url}
                  target='_blank'
                  className='text-indigo-600 underline'
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

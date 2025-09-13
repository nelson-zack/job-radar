type Props = {
  page: number; // zero-based
  totalPages: number; // total pages (>= 1)
  makeHref: (p: number) => string; // builds URL for a given page
};

export default function Pagination({ page, totalPages, makeHref }: Props) {
  const prevPage = Math.max(0, page - 1);
  const nextPage = Math.min(totalPages - 1, page + 1);
  const hasPrev = page > 0;
  const hasNext = page + 1 < totalPages;

  const linkBase =
    'px-3 py-1.5 rounded border border-[var(--line)] text-sm hover:bg-[var(--surface-1)]';
  const disabled = 'opacity-40 pointer-events-none';

  return (
    <nav
      className='flex items-center justify-between mt-4'
      aria-label='Pagination'
    >
      <a
        href={hasPrev ? makeHref(prevPage) : '#'}
        aria-disabled={!hasPrev}
        className={`${linkBase} ${!hasPrev ? disabled : ''}`}
      >
        ← Prev
      </a>

      <span className='text-xs text-[var(--muted)]'>
        Page {page + 1} of {Math.max(1, totalPages)}
      </span>

      <a
        href={hasNext ? makeHref(nextPage) : '#'}
        aria-disabled={!hasNext}
        className={`${linkBase} ${!hasNext ? disabled : ''}`}
      >
        Next →
      </a>
    </nav>
  );
}

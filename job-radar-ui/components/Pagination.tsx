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
    'inline-flex items-center gap-1 rounded-full border border-[var(--border)]/60 bg-[var(--surface-3)]/70 px-3.5 py-1.75 text-sm font-semibold text-[var(--text)] transition-colors hover:border-[var(--accent)] hover:text-[var(--accent)]';
  const disabled = 'opacity-40 pointer-events-none';

  return (
    <nav
      className='mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between'
      aria-label='Pagination'
    >
      <div className='flex items-center gap-2'>
        <a
          href={hasPrev ? makeHref(prevPage) : '#'}
          aria-disabled={!hasPrev}
          className={`${linkBase} ${!hasPrev ? disabled : ''}`}
        >
          ← Prev
        </a>

        <a
          href={hasNext ? makeHref(nextPage) : '#'}
          aria-disabled={!hasNext}
          className={`${linkBase} ${!hasNext ? disabled : ''}`}
        >
          Next →
        </a>
      </div>

      <span className='rounded-full border border-[var(--border)]/50 bg-[var(--surface-3)]/70 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-[var(--muted)] shadow-[var(--shadow-sm)]'>
        Page {page + 1} of {Math.max(1, totalPages)}
      </span>
    </nav>
  );
}

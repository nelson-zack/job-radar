// hooks/usePagination.ts
'use client';

import { useMemo, useState } from 'react';

type Options = {
  initialPage?: number;
  limit?: number;
  total?: number; // optional; if provided we compute totalPages
};

export function usePagination({
  initialPage = 1,
  limit = 25,
  total
}: Options = {}) {
  const [page, setPage] = useState(initialPage);

  const offset = useMemo(() => (page - 1) * limit, [page, limit]);
  const totalPages = useMemo(
    () => (total ? Math.max(1, Math.ceil(total / limit)) : undefined),
    [total, limit]
  );

  function next() {
    if (totalPages) setPage((p) => Math.min(totalPages, p + 1));
    else setPage((p) => p + 1);
  }
  function prev() {
    setPage((p) => Math.max(1, p - 1));
  }

  return { page, setPage, limit, offset, totalPages, next, prev };
}

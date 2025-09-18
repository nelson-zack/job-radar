import { API_BASE_URL, IS_PUBLIC_READONLY } from '../utils/env';
// lib/api.ts
export type Job = {
  id: number;
  company: string;
  company_name: string;
  title: string;
  level: string;
  is_remote: boolean;
  posted_at: string | null;
  url: string;
};

export type JobsResponse = {
  items: Job[];
  total: number;
  limit: number;
  offset: number;
};

type QueryParams = Record<string, string | number | boolean | undefined>;

type ApiFetchOptions = (RequestInit & { query?: QueryParams }) & {
  // Next.js extends RequestInit with `next`
  next?: { revalidate?: number };
};

const WRITE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export function buildApiUrl(path: string, query: QueryParams = {}): string {
  const isAbsolute = /^https?:\/\//i.test(path);
  const normalized = isAbsolute
    ? path
    : `${API_BASE_URL}${path.startsWith('/') ? '' : '/'}${path}`;
  const url = new URL(normalized);
  Object.entries(query).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      url.searchParams.set(key, String(value));
    }
  });
  return url.toString();
}

export async function apiFetch(path: string, options: ApiFetchOptions = {}) {
  const { query, ...init } = options;
  const method = (init.method ?? 'GET').toUpperCase();
  if (WRITE_METHODS.has(method) && IS_PUBLIC_READONLY) {
    throw new Error('Writes are disabled in PUBLIC_READONLY mode.');
  }

  const url = buildApiUrl(path, query);
  return fetch(url, init);
}

export async function fetchJobs(
  params: Record<string, string | number | boolean | undefined> = {}
) {
  const r = await apiFetch('/jobs', {
    query: params,
    cache: 'no-store',
    next: { revalidate: 0 }
  });
  if (!r.ok) {
    const body = await r.text().catch(() => '');
    const errorUrl = r.url || buildApiUrl('/jobs', params);
    throw new Error(`Failed to fetch jobs (${r.status}): ${body}\nURL: ${errorUrl}`);
  }
  return r.json() as Promise<JobsResponse>;
}

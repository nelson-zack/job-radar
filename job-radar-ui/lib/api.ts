import { API_BASE_URL, IS_PUBLIC_READONLY } from '../utils/env';

const DEFAULT_FETCH_TIMEOUT = Number(
  process.env.NEXT_PUBLIC_FETCH_TIMEOUT_MS ||
    process.env.FETCH_TIMEOUT_MS ||
    15000
);

function emitApiError(message: string) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent('job-radar-api-error', {
      detail: { message }
    })
  );
}

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
  const { query, signal: providedSignal, ...init } = options;
  const method = (init.method ?? 'GET').toUpperCase();
  if (WRITE_METHODS.has(method) && IS_PUBLIC_READONLY) {
    throw new Error('Writes are disabled in PUBLIC_READONLY mode.');
  }

  const url = buildApiUrl(path, query);
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  let controller: AbortController | undefined;
  let signal = providedSignal;
  const timeoutMs = Number.isFinite(DEFAULT_FETCH_TIMEOUT)
    ? Number(DEFAULT_FETCH_TIMEOUT)
    : 15000;

  if (!signal && typeof AbortController !== 'undefined' && timeoutMs > 0) {
    controller = new AbortController();
    timeoutId = setTimeout(() => controller?.abort(), timeoutMs);
    signal = controller.signal;
  }

  try {
    return await fetch(url, { ...init, signal });
  } catch (error) {
    const message =
      error instanceof Error
        ? error.name === 'AbortError'
          ? `Request timed out after ${timeoutMs}ms`
          : error.message
        : 'Request failed';
    emitApiError(message);
    throw error instanceof Error && error.name === 'AbortError'
      ? new Error(message)
      : error;
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
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
    emitApiError('Unable to load jobs. Please retry in a moment.');
    throw new Error(`Failed to fetch jobs (${r.status}): ${body}\nURL: ${errorUrl}`);
  }
  return r.json() as Promise<JobsResponse>;
}

import { API_URL } from '@/utils/env';
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

export async function fetchJobs(
  params: Record<string, string | number | boolean | undefined> = {}
) {
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') qs.set(k, String(v));
  });

  const url = `${API_URL}/jobs?${qs.toString()}`;

  const r = await fetch(url, { cache: 'no-store', next: { revalidate: 0 } });
  if (!r.ok) {
    const body = await r.text().catch(() => '');
    throw new Error(`Failed to fetch jobs (${r.status}): ${body}\nURL: ${url}`);
  }
  return r.json() as Promise<JobsResponse>;
}

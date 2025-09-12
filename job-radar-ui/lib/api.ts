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
  const base = process.env.NEXT_PUBLIC_API_URL!;
  const qs = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') qs.set(k, String(v));
  });
  const r = await fetch(`${base}/jobs?${qs.toString()}`, { cache: 'no-store' });
  if (!r.ok) throw new Error(`Failed to fetch jobs (${r.status})`);
  return r.json() as Promise<JobsResponse>;
}

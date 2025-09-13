export type Job = {
  id: number;
  company: string;
  company_name?: string;
  title: string;
  level?: string | null;
  is_remote: boolean;
  posted_at?: string | null;
  url: string;
};
export type JobsResponse = {
  items: Job[];
  total: number;
  limit: number;
  offset: number;
};

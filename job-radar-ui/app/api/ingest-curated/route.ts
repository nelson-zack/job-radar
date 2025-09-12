// app/api/ingest-curated/route.ts
export async function POST() {
  const api = process.env.NEXT_PUBLIC_API_URL!;
  const token = process.env.RADAR_ADMIN_TOKEN ?? '';
  const r = await fetch(`${api}/ingest/curated`, {
    method: 'POST',
    headers: { 'x-token': token, Accept: 'application/json' },
    cache: 'no-store'
  });
  const body = await r.text(); // in case API returns non-JSON on errors
  return new Response(body, {
    status: r.status,
    headers: { 'content-type': 'application/json' }
  });
}

import { test } from 'node:test';
import assert from 'node:assert/strict';

function resetModules() {
  const apiPath = require.resolve('../lib/api');
  const envPath = require.resolve('../utils/env');
  delete require.cache[apiPath];
  delete require.cache[envPath];
}

async function importApi() {
  resetModules();
  return require('../lib/api') as typeof import('../lib/api');
}

test('buildApiUrl respects NEXT_PUBLIC_API_BASE_URL', async () => {
  process.env.NEXT_PUBLIC_API_BASE_URL = 'https://example.com/base';
  delete process.env.NEXT_PUBLIC_API_URL;
  process.env.PUBLIC_READONLY = 'false';
  const api = await importApi();
  const url = api.buildApiUrl('/jobs', { limit: 5, empty: '' });
  assert.equal(url, 'https://example.com/base/jobs?limit=5');
});

test('apiFetch blocks write methods when PUBLIC_READONLY is true', async () => {
  process.env.NEXT_PUBLIC_API_BASE_URL = 'https://example.com';
  process.env.PUBLIC_READONLY = 'true';
  const api = await importApi();
  await assert.rejects(
    api.apiFetch('/ingest/curated', { method: 'POST' }),
    /PUBLIC_READONLY/i
  );
});

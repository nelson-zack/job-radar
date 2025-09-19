import { test } from 'node:test';
import assert from 'node:assert/strict';

import { getVisibleProviders } from '../lib/providers';

test('getVisibleProviders returns supported providers when experimental disabled', () => {
  const providers = getVisibleProviders(false);
  assert.deepEqual(providers, ['all', 'greenhouse']);
});

test('getVisibleProviders includes experimental providers when enabled', () => {
  const providers = getVisibleProviders(true);
  assert(providers.includes('ashby'));
});

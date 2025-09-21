import { test } from 'node:test';
import assert from 'node:assert/strict';
import { renderToStaticMarkup } from 'react-dom/server';
import React from 'react';
import Module from 'module';
import path from 'node:path';

type ResolveFn = (request: string, parent: NodeModule | undefined, isMain: boolean, options: unknown) => string;
const moduleWithResolve = Module as unknown as { _resolveFilename: ResolveFn };
const originalResolveFilename = moduleWithResolve._resolveFilename;

moduleWithResolve._resolveFilename = function (
  request: string,
  parent: NodeModule | undefined,
  isMain: boolean,
  options: unknown
) {
  if (request === 'next/navigation') {
    const mapped = path.resolve(__dirname, './stubs/next-navigation');
    return originalResolveFilename.call(this, mapped, parent, isMain, options);
  }
  if (request.startsWith('@/')) {
    const mapped = path.resolve(__dirname, '..', request.slice(2));
    return originalResolveFilename.call(this, mapped, parent, isMain, options);
  }
  return originalResolveFilename.call(this, request, parent, isMain, options);
};

const FiltersBar = require('../components/FiltersBar').default as typeof import('../components/FiltersBar').default;

test('provider filter visible by default', () => {
  const prev = process.env.NEXT_PUBLIC_SHOW_PROVIDER_FILTER;
  delete process.env.NEXT_PUBLIC_SHOW_PROVIDER_FILTER;

  const html = renderToStaticMarkup(
    React.createElement(FiltersBar, { providers: ['all', 'greenhouse', 'ashby'] })
  );

  assert(html.includes('Provider'));

  if (prev === undefined) delete process.env.NEXT_PUBLIC_SHOW_PROVIDER_FILTER;
  else process.env.NEXT_PUBLIC_SHOW_PROVIDER_FILTER = prev;
});

test('provider filter hidden when flag disabled', () => {
  const prev = process.env.NEXT_PUBLIC_SHOW_PROVIDER_FILTER;
  process.env.NEXT_PUBLIC_SHOW_PROVIDER_FILTER = 'false';

  const html = renderToStaticMarkup(
    React.createElement(FiltersBar, { providers: ['all', 'greenhouse', 'ashby'] })
  );

  assert(!html.includes('Provider'));

  if (prev === undefined) delete process.env.NEXT_PUBLIC_SHOW_PROVIDER_FILTER;
  else process.env.NEXT_PUBLIC_SHOW_PROVIDER_FILTER = prev;
});

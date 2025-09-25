import { ENABLE_EXPERIMENTAL } from '../utils/env';

export const PROVIDER_STATUS: Record<string, 'supported' | 'experimental' | 'planned'> = {
  greenhouse: 'supported',
  github: 'supported',
  ashby: 'experimental',
  workday: 'experimental',
  lever: 'experimental',
  microsoft: 'planned',
  coalition: 'planned'
};

export function getVisibleProviders(enableExperimental: boolean = ENABLE_EXPERIMENTAL): string[] {
  const supported = Object.entries(PROVIDER_STATUS)
    .filter(([, status]) => status === 'supported')
    .map(([name]) => name);
  const experimental = Object.entries(PROVIDER_STATUS)
    .filter(([, status]) => status === 'experimental')
    .map(([name]) => name);

  const base = ['all', ...supported];
  if (enableExperimental) {
    base.push(...experimental);
  }
  return Array.from(new Set(base));
}

export function showProviderFilter(): boolean {
  const v = process.env.NEXT_PUBLIC_SHOW_PROVIDER_FILTER;
  return v === undefined || v.toLowerCase() !== 'false';
}

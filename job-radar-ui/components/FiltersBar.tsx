'use client';

import { ENABLE_EXPERIMENTAL } from '@/utils/env';
import { useState } from 'react';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Select } from './ui/Select';
import { ALLOWED_ORDERS_SET, type Order } from '@/lib/sort';

type Props = {
  initialLevel?: string;
  initialSkills?: string;
  initialProvider?: string;
  providers?: string[];

  /** e.g. 'id_desc' | 'posted_at_desc' | 'posted_at_asc' */
  initialOrder?: Order;
};

export default function FiltersBar({
  initialLevel = 'any',
  initialSkills = '',
  initialOrder = 'posted_at_desc',
  initialProvider = 'all',
  providers = ['all', 'greenhouse']
}: Props) {
  const providerList = providers && providers.length ? providers : ['all', 'greenhouse'];
  const [provider, setProvider] = useState(initialProvider);
  let visibleProviders = providerList.filter((name) =>
    ENABLE_EXPERIMENTAL || name === 'all' || name === 'greenhouse'
  );
  if (provider && !visibleProviders.includes(provider)) {
    visibleProviders = [provider, ...visibleProviders];
  }
  const [lvl, setLvl] = useState(initialLevel || 'any');
  const [sk, setSk] = useState(initialSkills || '');
  const safeInitialOrder: Order =
    initialOrder && ALLOWED_ORDERS_SET.has(initialOrder)
      ? initialOrder
      : 'posted_at_desc';
  const [order, setOrder] = useState<Order>(safeInitialOrder);

  const router = useRouter();
  const pathname = usePathname();
  const sp = useSearchParams();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const params = new URLSearchParams(sp?.toString() || '');
    // Only include level if it isn't "any"
    const normalizedLevel = (lvl || 'any').toLowerCase();
    if (normalizedLevel === 'any') {
      params.delete('level');
    } else {
      params.set('level', normalizedLevel);
    }
    if (provider && provider !== 'all') params.set('provider', provider);
    else params.delete('provider');
    const safeOrder: Order = ALLOWED_ORDERS_SET.has(order)
      ? order
      : 'posted_at_desc';
    params.set('order', safeOrder);
    // skills
    const trimmed = sk.trim();
    if (trimmed) params.set('skills', trimmed);
    else params.delete('skills');
    // reset pagination when changing filters
    params.set('page', '0');
    router.push(`${pathname}?${params.toString()}`);
  }

  function handleReset() {
    setLvl('any');
    setSk('');
    setOrder('posted_at_desc');
    setProvider('all');
    router.push(pathname); // drop all query params
  }

  return (
    <section className='mb-6 rounded-2xl border border-[var(--border)]/60 bg-[var(--surface-3)]/70 backdrop-blur-xl shadow-[var(--shadow-md)] p-4 sm:p-6'>
      <form
        onSubmit={handleSubmit}
        className='grid w-full grid-cols-1 gap-4 items-stretch md:grid-cols-[minmax(140px,1fr)_minmax(220px,2fr)_minmax(160px,1fr)_minmax(160px,1fr)_auto]'
      >
        <div className='flex h-full flex-col justify-end gap-2 text-left'>
          <label className='block text-[0.7rem] font-semibold tracking-wide uppercase text-[var(--muted)]'>
            Level
          </label>
          <Select
            value={lvl}
            onChange={(e) => setLvl(e.target.value)}
            className='w-full'
          >
            <option value='any'>Any</option>
            <option value='junior'>Junior</option>
            <option value='mid'>Mid</option>
            <option value='senior'>Senior</option>
          </Select>
        </div>

        <div className='flex h-full flex-col justify-end gap-2'>
          <label className='block text-[0.7rem] font-semibold tracking-wide uppercase text-[var(--muted)]'>
            Skills (any)
          </label>
          <Input
            value={sk}
            onChange={(e) => setSk(e.target.value)}
            placeholder='python, react, sql'
            className='w-full'
          />
        </div>

        <div className='flex h-full flex-col justify-end gap-2'>
          <label className='block text-[0.7rem] font-semibold tracking-wide uppercase text-[var(--muted)]'>
            Sort
          </label>
          <Select
            value={order}
            onChange={(e) => {
              const v = e.target.value as Order;
              setOrder(ALLOWED_ORDERS_SET.has(v) ? v : 'posted_at_desc');
            }}
            className='w-full'
          >
            <option value='posted_at_desc'>Newest</option>
            <option value='posted_at_asc'>Oldest</option>
          </Select>
        </div>
        <div className='flex h-full flex-col justify-end gap-2'>
          <label className='block text-[0.7rem] font-semibold tracking-wide uppercase text-[var(--muted)]'>
            Provider
          </label>
          <Select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className='w-full'
          >
            {visibleProviders.map((name) => (
              <option key={name} value={name}>
                {name === 'all' ? 'All providers' : name}
              </option>
            ))}
          </Select>
        </div>


        <div className='flex h-full items-end justify-end gap-2 self-stretch sm:gap-3'>
          <Button type='button' variant='ghost' onClick={handleReset}>
            Reset
          </Button>
          <Button type='submit'>Search</Button>
        </div>
      </form>
    </section>
  );
}

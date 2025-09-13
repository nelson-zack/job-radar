'use client';
import { useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Select } from './ui/Select';

type Props = {
  /** starting value for the level dropdown (e.g. "any", "junior", …) */
  initialLevel?: string;
  /** starting value for the skills input (comma-separated) */
  initialSkills?: string;
};

export default function FiltersBar({
  initialLevel = 'any',
  initialSkills = ''
}: Props) {
  const [lvl, setLvl] = useState(initialLevel || 'any');
  const [sk, setSk] = useState(initialSkills || '');
  const router = useRouter();
  const pathname = usePathname();

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const params = new URLSearchParams();
    if (lvl && lvl.toLowerCase() !== 'any') {
      params.set('level', lvl.toLowerCase());
    }
    if (sk.trim()) {
      params.set('skills', sk.trim());
    }
    // always reset to first page on a new search
    params.set('page', '0');
    router.push(`${pathname}?${params.toString()}`);
  }

  return (
    <form
      className='mb-4 flex flex-wrap items-end gap-3'
      onSubmit={handleSubmit}
    >
      <div>
        <label className='block text-xs font-medium mb-1'>Level</label>
        <Select
          value={lvl}
          onChange={(e) => setLvl(e.target.value)}
          className='min-w-[120px]'
        >
          <option value='any'>Any</option>
          <option value='junior'>Junior</option>
          <option value='mid'>Mid</option>
          <option value='senior'>Senior</option>
        </Select>
      </div>

      <div className='flex-1 min-w-[220px]'>
        <label className='block text-xs font-medium mb-1'>Skills (any)</label>
        <Input
          value={sk}
          onChange={(e) => setSk(e.target.value)}
          placeholder='python, react, sql'
        />
      </div>

      <Button type='submit'>Search</Button>
    </form>
  );
}

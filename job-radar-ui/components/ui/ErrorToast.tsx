'use client';

import { useEffect, useRef, useState } from 'react';

const EVENT_NAME = 'job-radar-api-error';
const DISPLAY_MS = 5000;

type EventDetail = {
  message?: string;
};

type ApiErrorEvent = CustomEvent<EventDetail>;

export default function ErrorToast() {
  const [message, setMessage] = useState<string | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    function handle(event: Event) {
      const detail = (event as ApiErrorEvent).detail || {};
      const nextMessage = detail.message || 'Request failed. Please try again.';
      setMessage(nextMessage);
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = setTimeout(() => {
        setMessage(null);
      }, DISPLAY_MS);
    }

    window.addEventListener(EVENT_NAME, handle as EventListener);
    return () => {
      window.removeEventListener(EVENT_NAME, handle as EventListener);
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  if (!message) return null;

  return (
    <div className='pointer-events-none fixed inset-x-0 top-4 z-[9999] flex justify-center px-4 sm:px-0'>
      <div className='pointer-events-auto max-w-md rounded-xl border border-[var(--border)]/70 bg-[var(--surface-3)]/95 px-4 py-3 text-sm text-[var(--text)] shadow-[var(--shadow-lg)] backdrop-blur-md'>
        {message}
      </div>
    </div>
  );
}

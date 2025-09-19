// utils/env.ts
const baseCandidate =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.API_BASE_URL ||
  'http://localhost:8000';

export const API_BASE_URL = baseCandidate.replace(/\/+$/, '');
// Back-compat for older imports
export const API_URL = API_BASE_URL;

const readonlyCandidate =
  process.env.PUBLIC_READONLY ??
  process.env.NEXT_PUBLIC_PUBLIC_READONLY ??
  'false';

export const IS_PUBLIC_READONLY =
  typeof readonlyCandidate === 'string'
    ? readonlyCandidate.toLowerCase() === 'true'
    : Boolean(readonlyCandidate);

export const ENABLE_EXPERIMENTAL = (process.env.NEXT_PUBLIC_ENABLE_EXPERIMENTAL || process.env.ENABLE_EXPERIMENTAL || "false").toLowerCase() === "true";

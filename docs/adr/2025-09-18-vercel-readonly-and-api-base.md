# ADR 2025-09-18: Vercel Read-only Toggle and API Base URL

## Problem

The UI currently hardcodes the API origin (`NEXT_PUBLIC_API_URL`) and always exposes write actions (e.g., curated ingest) regardless of deployment target. For Vercel, we need:
- A configurable base URL pointing to the Render API without per-call string concatenation drift.
- A public read-only mode so demo deployments do not allow state-changing requests.

## Options Considered

1. **Introduce `NEXT_PUBLIC_API_BASE_URL` and `PUBLIC_READONLY` envs** (preferred):
   - Reuse the existing env util, add a write guard in the API client, and hide write controls in the UI when read-only.
2. Continue using `NEXT_PUBLIC_API_URL` and add per-component guards.
3. Proxy all writes through a new API route that enforces read-only (requires backend updates).

## Decision

Adopt option 1. Centralize base URL construction via a shared helper. Add a compile-time `PUBLIC_READONLY` flag that prevents client write calls and removes write controls. Keep response shapes untouched.

## Feature Flags / Env

- `NEXT_PUBLIC_API_BASE_URL`: absolute origin for API requests (falls back to `NEXT_PUBLIC_API_URL` and local default).
- `PUBLIC_READONLY` (default `false`): when truthy, UI write actions are hidden/disabled and client calls to write endpoints throw.

## Risks & Mitigations

- **Forgotten env in deployment**: Document defaults in README and `.env.example` with fallbacks to preserve local behavior.
- **Client/server env drift**: Expose `PUBLIC_READONLY` through Next config and fall back to `false` to avoid hydration mismatches.
- **Future write surfaces**: Require new write helpers to import the shared guard to maintain consistency.

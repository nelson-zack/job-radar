# ADR 2025-09-18: Entry-Level Exclusion Filter

## Problem

We want the public Vercel deployment of Job Radar to suppress mid/senior roles by default without changing the API response shape. The existing ingestion heuristics rank junior titles but still persist higher-level jobs, and the `/jobs` API simply paginates whatever is stored. We need a configurable server-side guard that hides obvious senior roles and 3+ year requirements while keeping the API contract intact.

## Options Considered

1. **Entry filter shared between ingestion and API (chosen)**
   - Add a reusable `filter_entry_level` helper, gate it behind a feature flag, and reuse it in both the Greenhouse fetcher and the `/jobs` endpoint. Adds metrics logging and keeps the response schema unchanged.
2. Title-only exclusion in SQL
   - Simple to implement but misses 3+ years requirements in descriptions; would still leak higher-level roles.
3. Full rewrite of provider pipelines to tag exclusions at ingest time only
   - Would not protect legacy records already in the database and complicates future provider additions.

## Decision

Adopt option 1. Introduce `FILTER_ENTRY_EXCLUSIONS` as an env-guarded feature. When enabled, the backend removes obvious senior titles and ≥3+ years requirements during ingestion and query time. Counts are logged per provider for observability, and the API keeps its existing payload fields.

## Feature Flags / Env

- `FILTER_ENTRY_EXCLUSIONS` (default `false`): if set to `true`, enforce the exclusion filter during ingestion and `/jobs` responses.

## Risks & Mitigations

- **Filter false positives**: log exclusion reasons and keep additive tests for representative titles/descriptions.
- **Legacy data drift**: `/jobs` applies the same filter so older rows are suppressed when the flag is enabled.
- **Performance impact**: SQL filters and limited text pattern checks keep the added cost low; fallback filtering happens in Python only when necessary.

# ADR 2025-09-18: GitHub Posted-At Inference

## Problem

GitHub-curated job listings enter the system without a timestamp. That causes the public feed to show “unknown” dates and breaks the Recent view. We need a backend-only solution that infers a posting date so undated entries are either populated or hidden, while keeping API schemas intact.

## Options Considered

1. **Infer using repository history (chosen)**
   - Inspect the PR merge date, then commit add date, then the latest touch date, and store the first available timestamp.
   - Gate behind a feature flag and exclude undated rows from `/jobs` unless the client opts in.
2. Require manual curation metadata in the GitHub sources.
   - Would add friction and dependence on upstream maintainers.
3. Keep status quo but push the filtering to the client/UI.
   - Leaves backend data noisy and makes recent filtering unreliable.

## Decision

Adopt option 1. Add `GITHUB_DATE_INFERENCE` flag. When enabled, the GitHub provider calls a helper that looks at PR merge dates, commit add dates, then last-touch commits. Store the inferred `posted_at` when available and log counts for observability. In the `/jobs` endpoint, hide undated rows by default (with `include_undated=true` escape hatch) to avoid surfacing stale entries.

## Feature Flags / Env

- `GITHUB_DATE_INFERENCE` (default `false`): enables date inference and default hiding of undated rows unless `include_undated=true`.

## Risks & Mitigations

- **Ambiguous git history**: fallback chain includes the latest touch date and logs undated counts so we can monitor.
- **Performance impacts**: inference helper is designed to accept injected git context; provider can cache metadata to avoid redundant lookups.
- **False dates**: merge/commit times may lag the actual posting; risk acceptable compared to unknown dates.

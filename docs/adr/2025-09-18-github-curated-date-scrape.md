# ADR 2025-09-18: GitHub Curated Date Scrape

## Problem

Curated GitHub job lists include human-readable date or age columns, but the provider currently ignores them. Posted dates remain null unless git-history inference is enabled, which makes recent filtering unreliable when scrape data already includes explicit timing.

## Options Considered

1. Parse the curated table/list date column during ingestion (chosen).
2. Continue relying on git-history inference and ignore explicit dates.
3. Require manual annotations in the repo via custom metadata.

## Decision

Add a `GITHUB_CURATED_DATE_SCRAPE` flag. When enabled, the provider parses the date/age column into an absolute UTC `posted_at`. Git-history inference remains as a fallback if the scrape lacks dates. Metrics report parsed, inferred, and undated counts.

## Feature Flags / Env

- `GITHUB_CURATED_DATE_SCRAPE` (default `false`): activates date parsing from curated sources.
- `GITHUB_DATE_INFERENCE` remains available as a fallback.

## Risks & Mitigations

- **Format drift**: parsing helper supports common patterns (ISO, `Sep 17`, `3d`, `2 days ago`) and can be extended.
- **Timezone ambiguity**: interpret as naive UTC; curated repos target US time zones, so relative errors are small.
- **Performance**: parsing happens inline and uses cached regex; negligible overhead.

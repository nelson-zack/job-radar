# ADR 2025-09-19: Metrics Endpoint

## Context

Stakeholders need ingestion health metrics (totals, exclusion signals, undated ratios, provider breakdowns) surfaced via the API without introducing new tables. The API should expose the metrics publicly when flagged, and otherwise reuse the admin token path. We also want a lightweight audit trail for emitting the metrics contract to the frontend team.

## Decision

- Add a FastAPI handler at `GET /metrics/ingestion` that computes counts directly from the existing jobs table.
- Reuse `filter_entry_level` to derive exclusion counts so the metrics stay aligned with our entry-level guardrails.
- Cache the last ingest trigger in-memory when `/ingest/curated` or `/scan/ats` run so the metrics payload includes an execution timestamp without schema changes.
- Gate access behind `METRICS_PUBLIC`; when `false` the endpoint demands the same `x-token` header as other admin routes.

## Consequences

- Metrics reflect live DB state on each request, so the endpoint will execute multiple aggregate queries per call; current volumes make this acceptable.
- Restarting the API process resets `last_ingest_at` to `null` until the next ingest run because the marker lives in process memory.
- UI and external dashboards can consume a stable JSON contract without additional migrations.

## Status

Accepted

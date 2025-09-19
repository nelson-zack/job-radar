# ADR 2025-09-19: Provider Status Gating

## Problem

Job Radar currently treats all providers equally. Some connectors are production-ready while others are experimental or planned. We need a simple way to hide experimental providers by default (for both API defaults and UI filters) while still allowing developers to access them explicitly or via a flag.

## Options Considered

1. **Status map + feature flag (chosen)**
   - Maintain a registry of provider statuses and gate visibility via `ENABLE_EXPERIMENTAL` (default false).
2. Hard-code an allowlist in the API.
3. Store status in the database and join on every query.

## Decision

Adopt option 1. Introduce `PROVIDER_STATUS` with `supported`/`experimental`/`planned` markers and add `ENABLE_EXPERIMENTAL` to toggle visibility. The API uses the map to filter default `/jobs` queries; the UI filters the provider list accordingly. Explicit provider filters always work.

## Feature Flags / Env

- `ENABLE_EXPERIMENTAL` (default `false`): surfaced in both backend and frontend builds to expose experimental providers when true.

## Risks & Mitigations

- **Status drift**: store the map centrally so both API and UI import the same values.
- **Confusion**: document the flag and the provider statuses, ensuring admin/dev paths work via explicit filters.

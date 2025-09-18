# Job Radar

**Current version:** 0.4.0 (Phase 3 kickoff)

> Surfaces remote-friendly early-career software roles by crawling applicant tracking systems (ATS), normalizing the data, and exposing the results via CLI, API, and a web dashboard.

## Contents

- [Overview](#overview)
- [Architecture at a Glance](#architecture-at-a-glance)
- [Progress Snapshot](#progress-snapshot)
- [Roadmap](#roadmap)
- [Quality & Engineering Practices](#quality--engineering-practices)
- [Getting Started](#getting-started)
- [Usage Reference](#usage-reference)
- [Known Limitations](#known-limitations)
- [Development Workflow](#development-workflow)

## Overview

- Crawls Greenhouse, Lever, Workday, Ashby, Workable, and curated GitHub sources to build a deduplicated job feed.
- Applies junior-friendly, remote-first filtering with skill scoring and recency controls to highlight actionable roles.
- Delivers results through a Python CLI, FastAPI service, and a Next.js UI that supports filtering, pagination, and admin actions.

## Architecture at a Glance

- **CLI & ingestion**: `job_radar.py` orchestrates provider crawlers, description enrichment, filtering, and deduplication.
- **Provider registry**: modular connectors live under `radar/providers`, making it straightforward to add or tune ATS integrations.
- **Persistence**: SQLAlchemy models (`Company`, `Job`, `JobSkill`, `CrawlRun`) target PostgreSQL (Docker) with SQLite support for quick local runs.
- **API**: FastAPI entrypoint (`radar/api/main.py`) exposes health probes, job and company endpoints, and admin ingestion triggers.
- **Web UI**: Next 15 application (`job-radar-ui`) fetches from the API, offers client filter controls, and includes an admin page for curated imports.
- **Config & data**: `companies.json`, `config/default_skills.json`, and environment variables drive provider settings, defaults, and admin security.

## Progress Snapshot

### Completed

- Provider normalization across Greenhouse, Lever, Workday, Ashby, and Workable with shared schema guarantees.
- Junior/remote filtering, recency gates, and skill scoring with CSV/JSON export support.
- Persistence layer and FastAPI service with typed responses, admin token protection, and ingestion endpoints.
- Curated GitHub ingestion flow wired into both the CLI and the admin endpoint.
- Next.js job browser foundation with server component data fetching, filter bar, pagination, and company/job tables.

### In Flight

- Polishing the web UI experience (empty/error states, loading feedback, shared TypeScript types to avoid duplication).
- Hardening admin actions by improving API error messaging and token-handling in the Next.js route.
- Capturing ingestion metrics and success diagnostics to surface in API responses and the UI.

### Up Next

- Expand exports and integrations (CSV presets, optional Slack/Sheets delivery, richer saved views).
- Scheduling and containerization for automated daily runs (cron wrappers, Docker Compose profiles).
- Automated QA: pytest coverage for provider adapters/API, contract tests for UI fetches, and CI wiring.

## Roadmap

| Phase | Status      | Focus                                       | Key Deliverables                                                     |
| ----- | ----------- | ------------------------------------------- | -------------------------------------------------------------------- |
| 0     | Done        | Baseline setup & repo hygiene               | Version control, company list, documentation shell                   |
| 1     | Done        | Provider normalization & filtering accuracy | Modular connectors, junior/remote heuristics, recency/skills filters |
| 2     | Done        | Persistence & minimal API                   | SQLAlchemy models, FastAPI service, admin token gating               |
| 2.5   | Done        | Curated GitHub ingestion                    | Import pipeline for remote new-grad lists, CLI + API wiring          |
| 3     | In progress | Web experience & export polish              | Next.js UI refinements, CSV customization, admin actions UX          |
| 4     | Planned     | Scheduling & containerization               | Docker image(s), Compose stack, cron/task automation                 |
| 5     | Planned     | Integrations & notifications                | Slack/email hooks, Google Sheets sync, webhook surface               |
| 6     | Planned     | Performance & resilience                    | Provider rate-limit handling, caching, observability                 |
| 7     | Planned     | Automation & QA                             | Test suite coverage, CI/CD, coding standards enforcement             |

## Quality & Engineering Practices

- **Strengths**: modular provider registry with shared normalization, typed FastAPI responses with dependency-injected sessions, and a Next.js UI that leans on server components, accessible table markup, and centralized env handling.
- **Currently tightening**: align shared TypeScript models (`lib/types` vs `lib/api`), add resilient error and loading states in the UI, and document environment variables (`DATABASE_URL`, `RADAR_ADMIN_TOKEN`, `NEXT_PUBLIC_API_BASE_URL`, `PUBLIC_READONLY`).
- **Next quality investments**: expand pytest coverage (providers, filters, API contracts), add regression tests for CLI flags, wire `npm run lint` and backend checks into CI, and introduce structured logging/metrics for ingestion runs.

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+ (for the Next.js UI)
- Docker (recommended for local PostgreSQL) or access to a PostgreSQL instance

### Backend & CLI

1. Create and activate a virtual environment:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run your first scan (junior-friendly filter enabled):

   ```bash
   python job_radar.py companies.json --junior-only
   ```

4. Relaxed junior mode and CSV export example:

   ```bash
   python job_radar.py companies.json --junior-only --relax --csv out.csv
   ```

### API Service

1. Configure environment (example `.env` snippet):

   ```bash
   export DATABASE_URL="postgresql+psycopg://radar:radar@localhost:5432/radar"
   export RADAR_ADMIN_TOKEN="super-secret-token"
   ```

2. Initialize the database schema:

   ```bash
   python scripts/init_db.py
   ```

3. Launch the API:

   ```bash
   uvicorn radar.api.main:app --reload
   ```

### Web UI (Next.js)

1. Install dependencies:

   ```bash
   cd job-radar-ui
   npm install
   ```

2. Create `.env.local` with:

   ```bash
   NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
   PUBLIC_READONLY=false
   RADAR_ADMIN_TOKEN=super-secret-token
   ```

3. Start the dev server:

   ```bash
   npm run dev
   ```

4. Visit `http://localhost:3000` for the job browser and `/admin` for admin actions.

### Database (PostgreSQL via Docker)

```bash
docker run --name radar-postgres -e POSTGRES_USER=radar -e POSTGRES_PASSWORD=radar \
  -e POSTGRES_DB=radar -p 5432:5432 -d postgres:16
```

## Usage Reference

### CLI filters & flags

- `--junior-only` limits to explicit junior/new-grad/entry-level titles.
- `--junior-only --relax` accepts early-career signals (<=3 years experience) found in descriptions.
- `--us-remote-only` and `--exclude-hybrid` enforce fully remote US-friendly roles.
- `--recent-days N` keeps jobs posted in the last `N` days (`--require-date` drops undated roles).
- `--skills-any "python,react"` and `--skills-all "python,sql"` apply soft scoring; add `--skills-hard` to enforce as filters.
- `--profile apply-now` sets a daily run preset (US remote, last 14 days, relaxed junior mode).
- `--profile research` broadens recency and skill filters for exploration.

### CSV and output customization

- Use `--csv-columns` to choose columns and order (defaults include `rank`, `company`, `title`, `provider`, `posted_at`, `skill_score`, `url`).
- Global description fetch caps: `RADAR_DESC_CAP`, `RADAR_DESC_TIMEOUT`, `RADAR_DESC_MAX_CHARS`.
- Per-provider description caps: `RADAR_DESC_CAP_GREENHOUSE`, `RADAR_DESC_CAP_LEVER`, `RADAR_DESC_CAP_WORKDAY`, `RADAR_DESC_CAP_ASHBY`, `RADAR_DESC_CAP_WORKABLE`.

### API endpoints

- `GET /healthz` – service status.
- `GET /jobs` – pagination, level/remote/provider/company filters, `skills_any`, `order=posted_at_desc|posted_at_asc|id_desc|id_asc`.
- `GET /jobs/{id}` – job detail with description and skills.
- `GET /companies` – company list with job counts.
- `POST /ingest/curated` – pulls curated GitHub repos (admin token required).
- `POST /scan/ats` – runs the CLI ingestion workflow (admin token required).

## Known Limitations

- Ashby and Workable connectors are wired but still rely on accurate tokens and may produce sparse results.
- Some ATS boards render via heavy client-side JavaScript, which the current requests-based fetcher does not execute.
- Workday tenants can rate-limit or vary JSON payloads; large Workday lists may require throttling or tailored parsing.
- Workable tenants that render postings client-side are not supported without a headless browser approach.

## Development Workflow

- Use feature branches and keep commits focused; document user-facing changes in this README or a future changelog.
- Run ingestion locally (`python job_radar.py ...`) after modifying providers or filters, and spot-check results.
- Run `pytest` (once the suite is in place), `npm run lint`, and `npm run test` before opening a PR.
- Keep environment variables out of version control; coordinate secrets via `.env` files ignored by git.
- Open issues for new providers, integration ideas, or UX polish to keep the roadmap transparent.

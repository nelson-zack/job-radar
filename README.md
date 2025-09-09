Remote Junior SWE Radar - Quick Start

**Current Version:** 0.2.0 (Phase 1 complete)

What this does

- Pulls job postings directly from company applicant tracking systems (ATS) instead of noisy job boards.
- Filters for junior-friendly titles and remote United States eligibility.
- Prints direct apply links so you avoid closed or generic career pages.

## Current Features

- **Provider normalization**: Modular connectors for Greenhouse, Lever, Workday, Ashby, and Workable. Note: Ashby and Workable are wired but experimental and may require further adjustments or more company tokens to yield results consistently.
- **Recency filtering**: `--recent-days N` keeps only roles posted within the last N days. Add `--require-date` to enforce strictness.
- **Description snippets**: Fetches up to a capped number of job pages per provider to extract a plain-text snippet, enabling smarter junior detection.
- **Junior-friendly filtering**: `--junior-only` with optional `--relax` mode checks both title and description.
- **Skills filters**: `--skills-any` and `--skills-all` check against title+description. By default these act as soft scoring (ranking results). Add `--skills-hard` to enforce as hard gates.
- **US-remote filtering**: `--us-remote-only` ensures listings are explicitly Remote (US). Enhanced detection in both location and description fields.
- **Diagnostics**: Summary output shows counts, with-date/recent diagnostics, description snippet counts, and skills filter matches/top results.
- **Output**: JSON outputs use ISO8601 for datetime fields to ensure compatibility. CSV export includes skill scoring, ranking, and customizable columns (--csv-columns).

- **Profiles**: Use `--profile apply-now` or `--profile research` to quickly apply sensible defaults for daily runs.
- **Per-provider description caps**: Environment variables `RADAR_DESC_CAP_GREENHOUSE`, `RADAR_DESC_CAP_LEVER`, `RADAR_DESC_CAP_WORKDAY`, `RADAR_DESC_CAP_ASHBY`, and `RADAR_DESC_CAP_WORKABLE` override the global `RADAR_DESC_CAP`.
- **CSV customization**: `--csv-columns` lets you choose which fields to export and in what order. New fields include `provider`, `company_token`, `company_priority`, `posted_days_ago`, `skill_score`, and `rank`.

Project layout

- job_radar.py - CLI that orchestrates fetching, filtering, and printing matches.
- radar/providers/ - Modular connectors (Greenhouse, Lever, Workday, Ashby, Workable).
- companies.json - Curated list of remote-friendly companies with ATS info.
- requirements.txt - Python dependencies.
- scripts/detect_ats.sh - Helper script to detect ATS and suggest companies.json entries.
- config/default_skills.json - Default skills configuration used if no skills flags are provided.

Step-by-step setup

1. Install Python 3.10+ on your machine.
2. Create a virtual environment.
   macOS/Linux:
   python3 -m venv .venv
   source .venv/bin/activate
   Windows (PowerShell):
   py -3 -m venv .venv
   .venv\Scripts\Activate.ps1

3. Install requirements:
   pip install -r requirements.txt

4. Run your first scan (junior-only filter on):
   python job_radar.py companies.json --junior-only

   # Relaxed junior mode:

   python job_radar.py companies.json --junior-only --relax

5. Review the output:

   - If there are matches, you will see lines like:
     - PostHog | Software Engineer I | Remote - US | https://boards.greenhouse.io/...
   - If you see "No matches found right now", rerun later or add more companies.

6. Add companies you want to watch:

   - Open companies.json.
   - For Greenhouse or Lever, grab the token from the job board URL once and add a new entry.
     Examples:
     Greenhouse: https://boards.greenhouse.io/vercel -> token "vercel"
     Lever: https://jobs.lever.co/snyk -> token "snyk"
   - For Workday, you need host and path. Example:
     DIRECTV: host directv.wd1.myworkdayjobs.com, path External
     The script will call the JSON endpoint at
     https://{host}/wday/cxs/{host}/{path}/jobs

   - For Ashby, the token is from jobs.ashbyhq.com/org/<token>.
   - For Workable, the token is the subdomain or path on apply.workable.com/<token>/.

7. Run it daily:
   macOS/Linux: use cron or launchd
   Windows: use Task Scheduler
   Example cron entry to run at 9:00 AM daily:
   0 9 \* \* \* /usr/bin/python3 /path/to/job_radar.py /path/to/companies.json --junior-only >> /path/to/radar.log 2>&1

Tuning the filters

- **Strict junior mode** (`--junior-only`): Accepts only titles with explicit junior signals — "junior", "new grad", "entry level", "software engineer i", or "associate" — and which clearly match engineering roles like Software Engineer/Developer (front end, back end, full‑stack, platform, web, mobile, data, ML, DevOps).
- **Relaxed junior mode** (`--junior-only --relax`): Also allows roles without explicit junior in the title if the description signals early‑career intent (e.g., “new grad,” “early career,” or ≤3 years experience). Senior/staff/lead titles and non‑engineering roles are still excluded.
- Senior, staff, principal, lead, manager, and other seniority titles are excluded in all modes.
- Non‑engineering titles (marketing, sales, account, operations, finance, legal, recruiting, design, architect, consultant, support, etc.) are excluded.
- US‑remote detection is location‑first: requires “Remote” + “United States” in the location, or if location is empty, requires both terms in the job page. Use `--us-remote-only` and `--exclude-hybrid` to strictly enforce.
- Use `--no-misfit-block` to include Security/Networking/Rust roles that are blocked by default.

- **Recency filtering** (`--recent-days N`): Keep only jobs posted in the last N days (default 0 = disabled). Use `--require-date` to drop jobs with no date.
- **Skills filters**:

  - `--skills-any "python,react,fastapi"` keeps jobs that mention any of the terms in the title or snippet.
  - `--skills-all "python,react"` keeps jobs that mention all listed terms.
  - By default, skills are used for ranking only. Add `--skills-hard` to drop jobs without matches.

- **Default skills config**:

  - If you don’t pass `--skills-any` or `--skills-all`, the tool will attempt to load defaults from a JSON file.
  - Search order:
    1. `--skills-defaults /path/to/file.json` (explicit path)
    2. `$RADAR_DEFAULT_SKILLS` environment variable (path)
    3. `config/default_skills.json` (repo default)
  - JSON format:
    ```json
    {
      "any": [
        "python",
        "react",
        "typescript",
        "node",
        "postgres",
        "sql",
        "django",
        "fastapi",
        "aws"
      ],
      "all": []
    }
    ```
  - On load, a message will print showing which defaults were applied.

- **Profiles**:

  - `--profile apply-now`: US remote only, last 14 days, junior-only with relaxed mode, min-score 1.
  - `--profile research`: Last 30 days, looser filters for exploration.
  - You can still override any defaults with explicit flags.

- **Per-provider description caps**:

  - By default, description fetching is capped globally with `RADAR_DESC_CAP`.
  - Override per provider with:
    - `RADAR_DESC_CAP_GREENHOUSE`
    - `RADAR_DESC_CAP_LEVER`
    - `RADAR_DESC_CAP_WORKDAY`
    - `RADAR_DESC_CAP_ASHBY`
    - `RADAR_DESC_CAP_WORKABLE`

- **CSV customization**:
  - Use `--csv-columns` to specify which columns to include and their order.
  - Default columns:
    `rank, company, title, location, source, provider, company_token, level, posted_at, posted_days_ago, skill_score, company_priority, url`
  - Customize per run, e.g.:
    ```bash
    python job_radar.py companies.json --profile apply-now \
      --csv-columns rank,company,title,provider,company_token,posted_days_ago,skill_score,url
    ```

Notes and tips

- Some ATS pages use dynamic content. The provided connectors work for many companies, but not all. Errors for a company will be logged and the scan continues.
- Workday endpoints sometimes rate-limit. If you add many Workday companies, consider spacing runs or adding sleep.
- If you want Google Sheets output or Slack/email alerts, I can provide an add-on module.

## Known Limitations

- Ashby and Workable connectors are implemented and wired, but currently most results come from Greenhouse. These providers may require more accurate tokens or further adjustments to yield consistent job listings.
- Some ATS boards use heavy JavaScript or dynamic rendering, which may not be fully supported with the current plain-requests approach.
- Workday endpoints are sometimes inconsistent or rate-limited, which can affect reliability for certain companies.
- Some Workable tenants only render job postings client-side with JavaScript. These may not be supported with the current plain-requests approach.

## Roadmap

### **Phase 0: Baseline Setup & Version Control**

- Establish a clean, maintainable codebase.
- Curate a reliable initial company list.
- Set up version control and documentation.

### **Phase 1: Provider Normalization & Filtering Accuracy** ✅

- Completed: modular connectors for multiple ATS providers, improved filtering accuracy, consistent schema across providers.

### **Phase 2: Filtering (junior, skills, recency, US remote)**

- Enhance junior-friendly filters.
- Add skills-based ranking and gating.
- Implement recency and US-remote filters.

_Next milestone: Phase 2 (Persistence + Minimal API) will introduce a Postgres schema and FastAPI service to persist jobs and serve results for both CLI and web UI._

### Phase 3: Persistence + Minimal API

- Add caching and data persistence.
- Provide a minimal API for job queries.

### Phase 4: Exports & Integrations (CSV, Google Sheets, Slack/email)

- Support CSV exports with skill scoring.
- Add integrations for Google Sheets and notifications.

### Phase 5: Scheduling + Containerization

- Enable scheduled runs via cron or similar.
- Containerize the application for easier deployment.

### Phase 6: Performance & Resilience

- Optimize runtime and resource usage.
- Improve error handling and retries.

### Phase 7: Dashboard (Optional)

- Develop a web dashboard for monitoring scans and results.

### Phase 8: Tests & CI

- Add unit and integration tests.
- Set up continuous integration pipelines.

Note: Ashby and Workable are implemented but currently Greenhouse provides the bulk of results.

Remote Junior SWE Radar - Quick Start

What this does

- Pulls job postings directly from company applicant tracking systems (ATS) instead of noisy job boards.
- Filters for junior-friendly titles and remote United States eligibility.
- Prints direct apply links so you avoid closed or generic career pages.

## Current Features

- **Provider normalization**: Modular connectors for Greenhouse, Lever, and Workday with consistent schema.
- **Recency filtering**: `--recent-days N` keeps only roles posted within the last N days. Add `--require-date` to enforce strictness.
- **Description snippets**: Fetches up to a capped number of job pages per provider to extract a plain-text snippet, enabling smarter junior detection.
- **Junior-friendly filtering**: `--junior-only` with optional `--relax` mode checks both title and description.
- **Skills filters**: `--skills-any` and `--skills-all` check against title+description. By default these act as soft scoring (ranking results). Add `--skills-hard` to enforce as hard gates.
- **US-remote filtering**: `--us-remote-only` ensures listings are explicitly Remote (US). Enhanced detection in both location and description fields.
- **Diagnostics**: Summary output shows counts, with-date/recent diagnostics, description snippet counts, and skills filter matches/top results.
- **Output**: JSON outputs use ISO8601 for datetime fields to ensure compatibility.
- **Profiles**: Use `--profile apply-now` or `--profile research` to quickly apply sensible defaults for daily runs.
- **Per-provider description caps**: Environment variables `RADAR_DESC_CAP_GREENHOUSE`, `RADAR_DESC_CAP_LEVER`, and `RADAR_DESC_CAP_WORKDAY` override the global `RADAR_DESC_CAP`.
- **CSV customization**: `--csv-columns` lets you choose which fields to export and in what order. New fields include `provider`, `company_token`, `company_priority`, `posted_days_ago`, `skill_score`, and `rank`.

Project layout

- job_radar.py - CLI that orchestrates fetching, filtering, and printing matches.
- providers.py - Connectors for Greenhouse, Lever, Ashby, and Workday.
- companies.json - Curated list of remote-friendly companies with ATS info.
- requirements.txt - Python dependencies.

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

## Roadmap

### Phase 0: Baseline Setup & Version Control

**What to build**

- Upload the project to a version control system (e.g., GitHub).
- Refine and prune the `companies.json` list to a high-confidence batch of ~50–100 companies.
- Remove inactive or low-yield companies.
- Prioritize companies with regular junior hiring, US-Remote eligibility, and clear ATS structure.

**Why it matters**

- Establishes a clean, maintainable codebase.
- Ensures the input data is relevant and reliable.
- Provides a foundation for iterative improvements.

**Deliverables**

- GitHub repository with initial commit.
- Curated `companies.json` file.
- Documentation for setup and usage.

**Example outcome**

- A stable starting point with a manageable and relevant company list, enabling predictable scan results.

---

### Phase 1: Filtering Accuracy & Clarity

**What to build**

- ✅ Added filtering summary at the end of each run (total jobs scanned, filtered out by rule, etc.).
- Improve false positive blocking (e.g., vague "Engineer" titles or misfit specialties).
- Refine US-remote detection with flexible matching and description fallback.
- ✅ Added recency, description snippets, and skills filters.

**Why it matters**

- Improves confidence in results.
- Provides transparency about filtering decisions.
- Reduces noise and irrelevant matches.

**Deliverables**

- Filtering summary output.
- Enhanced filtering logic.
- Better location and remote work detection.

**Example outcome**

- Clear reports showing how many jobs were found and filtered, with fewer irrelevant listings.

---

### Phase 2: Performance Optimization

**What to build**

- Optimize runtime by reducing slowdowns from HTML fetching and job parsing.
- Implement early exits, caching, and parallelization where possible.

**Why it matters**

- Speeds up scans, enabling more frequent or larger runs.
- Improves user experience with faster feedback.

**Deliverables**

- Refactored code with caching and concurrency.
- Benchmarks showing improved runtime.

**Example outcome**

- Scan times reduced from minutes to seconds for typical company lists.

---

### Phase 3: Expanded Provider Support

**What to build**

- Add support for the Remotive API.
- Add Teamtailor API integration.
- Add Greenhouse Job Board API Search (broad query mode).

**Why it matters**

- Increases coverage of job postings.
- Captures more remote junior roles from diverse sources.

**Deliverables**

- New provider modules for Remotive, Teamtailor, and enhanced Greenhouse.
- Updated documentation and tests.

**Example outcome**

- More comprehensive job listings from multiple ATS platforms.

---

### Phase 4: Output Enhancements

**What to build**

- Ensure clean TXT and CSV output in `/output` folder.
- Add optional Google Sheets export using `gspread` or Sheets API.

**Why it matters**

- Makes results easier to analyze, share, and archive.
- Supports integration with other tools and workflows.

**Deliverables**

- Export scripts for TXT, CSV, and Google Sheets.
- Configuration options for output formats.

**Example outcome**

- Users can easily open results in spreadsheets or automate reporting.

---

### Phase 5: Automation & Scheduling

**What to build**

- Add cron job (Mac/Linux) or Task Scheduler (Windows) setup instructions.
- Optional webhook/Slack/email summary alerts.
- Store previous run hashes to avoid duplicate alerts.

**Why it matters**

- Enables hands-off, regular scanning.
- Provides timely notifications about new matches.
- Prevents alert fatigue with deduplication.

**Deliverables**

- Automation scripts and documentation.
- Notification integration.
- State persistence for alerting.

**Example outcome**

- Daily scans with automatic alerts sent only when new jobs appear.

---

### Phase 6: Dev Experience & Testing

**What to build**

- Add unit tests for filtering logic.
- Add `test_data/` folder with sample ATS listings.
- Add `--dev-mode` to run a small subset of companies for quick tests.

**Why it matters**

- Improves code quality and reliability.
- Facilitates contributions and debugging.
- Speeds up development cycles.

**Deliverables**

- Test suite with coverage reports.
- Sample test data.
- Development mode flag.

**Example outcome**

- Confident code changes with minimal regressions.

---

### Phase 7: User-Specific Filtering

**What to build**

- Add optional filters based on tech stack, job type, or other user preferences.
- Allow configuration via command-line flags or config files.

**Why it matters**

- Tailors job matches to individual user needs.
- Reduces irrelevant listings further.

**Deliverables**

- Extended filtering options.
- User documentation.

**Example outcome**

- Users receive job matches aligned with their skills and interests.

---

### Phase 8: Improved Error Handling & Logging

**What to build**

- Enhance error reporting for failed company fetches.
- Implement retry logic for rate-limited endpoints.
- Provide detailed logs with configurable verbosity.

**Why it matters**

- Improves robustness and user troubleshooting.
- Helps identify and fix issues quickly.

**Deliverables**

- Robust logging system.
- Retry and backoff mechanisms.
- User guidance on error interpretation.

**Example outcome**

- Fewer scan interruptions and clearer diagnostics.

---

### Phase 9: Community & Collaboration Features

**What to build**

- Add support for community-contributed company entries.
- Implement a web dashboard for monitoring scans and results.
- Enable sharing of filtered job lists.

**Why it matters**

- Builds a user community around the tool.
- Enhances usability and engagement.
- Facilitates collaboration and sharing.

**Deliverables**

- Contribution guidelines.
- Web interface prototype.
- Sharing mechanisms.

**Example outcome**

- Active user base contributing companies and sharing job leads.

---

## Focus Order

If time or resources are limited, prioritize development in this order:

1. Baseline Setup & Version Control (Phase 0)
2. Filtering Accuracy & Clarity (Phase 1)
3. Performance Optimization (Phase 2)
4. Expanded Provider Support (Phase 3)
5. Output Enhancements (Phase 4)
6. Automation & Scheduling (Phase 5)
7. Dev Experience & Testing (Phase 6)
8. User-Specific Filtering (Phase 7)
9. Improved Error Handling & Logging (Phase 8)
10. Community & Collaboration Features (Phase 9)

This sequence builds a solid foundation first, improves core functionality and performance, then expands coverage and usability, and finally adds advanced features and community support.

Remote Junior SWE Radar - Quick Start

What this does

- Pulls job postings directly from company applicant tracking systems (ATS) instead of noisy job boards.
- Filters for junior-friendly titles and remote United States eligibility.
- Prints direct apply links so you avoid closed or generic career pages.

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

   python job_radar.py companies.json --junior-only --relax-junior

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
- **Relaxed junior mode** (`--junior-only --relax-junior`): Also allows roles without explicit junior in the title if the description signals early‑career intent (e.g., “new grad,” “early career,” or ≤3 years experience). Senior/staff/lead titles and non‑engineering roles are still excluded.
- Senior, staff, principal, lead, manager, and other seniority titles are excluded in all modes.
- Non‑engineering titles (marketing, sales, account, operations, finance, legal, recruiting, design, architect, consultant, support, etc.) are excluded.
- US‑remote detection is location‑first: requires “Remote” + “United States” in the location, or if location is empty, requires both terms in the job page. Use `--us-remote-only` and `--exclude-hybrid` to strictly enforce.
- Use `--no-misfit-block` to include Security/Networking/Rust roles that are blocked by default.

Notes and tips

- Some ATS pages use dynamic content. The provided connectors work for many companies, but not all. Errors for a company will be logged and the scan continues.
- Workday endpoints sometimes rate-limit. If you add many Workday companies, consider spacing runs or adding sleep.
- If you want Google Sheets output or Slack/email alerts, I can provide an add-on module.

## Roadmap

### ✅ Phase 1: Foundation & Version Control (Today)

**Goal:** Clean baseline, better inputs, and git-backed versioning

- [ ] Upload to GitHub (public or private)
- [ ] Polish `companies.json`  
      ▸ Manually prune/test and refine to a high-confidence batch of ~50–100 companies  
      ▸ Remove inactive or low-yield companies  
      ▸ Prioritize those with regular junior hiring, US-Remote eligibility, and clear ATS structure

---

### 🔧 Phase 2: MVP Polish

**Goal:** Improve accuracy, clarity, and usefulness of current output

- [ ] Add filtering summary at end of each run (total jobs scanned, filtered out by rule, etc.)
- [ ] Improve false positive blocking (e.g., vague "Engineer" titles or misfit specialties)
- [ ] Refine US-remote detection with flexible matching and description fallback

---

### 📤 Phase 3: Output Enhancements

**Goal:** Make results easier to use, share, and analyze

- [ ] Ensure clean TXT and CSV output in `/output` folder
- [ ] Optional Google Sheets export using `gspread` or Sheets API

---

### 🌐 Phase 4: New Providers (Expand Coverage)

**Goal:** Fetch jobs from more sources with minimal extra parsing

- [ ] Add Teamtailor support
- [ ] Add Remotive API
- [ ] Add Greenhouse Job Board API Search (broad query mode)

---

### ⚙️ Phase 5: Automation & Scheduling

**Goal:** Make it self-running and self-updating

- [ ] Add cron job (Mac/Linux) or Task Scheduler (Windows)
- [ ] Optional webhook/Slack/email summary alerts
- [ ] Store previous run hashes to avoid duplicate alerts

---

### 🧪 Phase 6: Dev Experience + Testing

**Goal:** Make the project easier to contribute to and test

- [ ] Add unit tests for filtering logic
- [ ] Add `test_data/` folder with sample ATS listings
- [ ] Add `--dev-mode` to run a small subset of companies for quick tests

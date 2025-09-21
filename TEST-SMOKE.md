# Job Radar Smoke Test Checklist

Run this checklist before sharing a build or demo. Use production URLs unless otherwise noted.

- [ ] **Desktop load**: Open the UI in a desktop browser, confirm the job list renders without console errors.
- [ ] **Mobile load**: Resize to a mobile viewport (or use device mode) and reload; ensure cards render correctly and navigation is usable.
- [ ] **Search**: Use the keyword search to find a known company or title; results should filter in-line.
- [ ] **Pagination**: Move forward and backward at least one page; totals and rows should update.
- [ ] **No senior roles (first 50)**: Scan the first two pages for titles that include "Senior", "Staff", "Principal", or "Manager"; flag if any appear.
- [ ] **Recent filter**: Apply the "Recent" or "Last N days" filter; verify every visible job has a posted date.
- [ ] **Include undated**: Enable the "Include undated" option and confirm previously hidden undated roles show up (and are marked appropriately).
- [ ] **Public read-only**: With `PUBLIC_READONLY=true`, attempt any write/admin action (ingest, admin page button); UI should disable the action and API calls should be rejected.

## Pass / Fail Notes

- Outcome: `PASS | FAIL`
- Issues found:
  -
  -


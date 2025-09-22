# Contributing Guidelines

Thanks for your interest in Job Radar! To keep things lightweight, contributors should:

1. Fork the repo and create a feature branch.
2. Install dependencies: `pip install -r requirements.txt` and `npm install` inside `job-radar-ui/`.
3. Run the test suite before opening a PR:
   - `python3 -m unittest discover tests -v`
   - `cd job-radar-ui && npm run lint && npm run test`
4. Ensure FastAPI endpoints remain backward compatible and keep public surfaces read-only by default.
5. Open a pull request that explains the change and links to any relevant issues.

We happily review small, focused patches—thanks for helping junior engineers find great roles!

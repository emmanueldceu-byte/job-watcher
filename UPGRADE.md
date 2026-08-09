# Upgrade your existing GitHub Job Watcher

You can keep the same repository, Pages URL, Gmail secret, and daily schedule.

Upload and overwrite these files from the new package:

- `config.json`
- `scraper.py`
- `notify.py`
- `docs/index.html`
- `docs/app.js`
- `.github/workflows/daily-jobs.yml`

Then commit to `main` and run **Actions → Daily job scan → Run workflow**.

The new version adds role-family matching, career-level classification, broader title discovery, career-level ranking, dashboard filters for Role Family and Level, and Node-24-compatible GitHub Pages action versions.

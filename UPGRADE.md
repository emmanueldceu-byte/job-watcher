# Deep Discovery Upgrade

This upgrade addresses low job counts caused by career sites that do not expose all jobs on the first HTML page.

## What changed
- Crawls multiple job-search/listing pages instead of only the first page.
- Uses career-site sitemaps when available to discover additional job detail URLs.
- Fetches job detail pages and reads JobPosting structured data when present.
- Can recognize generic employer titles (for example, Technology Analyst II) when the description clearly maps to cloud/security/IAM/GRC/IR/etc.
- Includes technical IC levels from intern/new-grad through lead/staff/principal/architect.
- Still excludes people-management/executive titles such as Manager, Director, VP, Chief, and Head of.
- Removes the old 7-year hard experience cap; seniority is now shown as a dashboard filter instead of deleting advanced IC roles.
- Adds per-company diagnostics to the GitHub Actions log: fetched, relevant, and location-matched counts.

## Update your existing GitHub repo
Replace only these files:
- `scraper.py`
- `config.json`

You do NOT need to edit your YAML workflow if your existing Daily job scan is already running successfully.

After committing the two files, go to Actions > Daily job scan > Run workflow.

Open the `Scan company career sites` step. You should now see lines like:

`Company Name: fetched 120 | relevant 9 | NYC/NJ or US-remote 5`

Those numbers make it easy to tell whether a specific employer's career system still needs a custom adapter.

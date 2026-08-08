# Healthcare Cloud & Cybersecurity Job Watcher — $0 Starter

A customized job-search web app that checks selected healthcare and health-technology company career pages every day, filters openings by **target role + cloud/security keyword**, and publishes the matches to a clean GitHub Pages site.

## What it does

- Runs automatically every day at **7:17 AM America/New_York**.
- Sends a **daily Gmail digest to `kingdomarmyknives@gmail.com`** after each scan once the Gmail App Password secret is added.
- Keeps only **NYC/North Jersey metro** opportunities or **fully remote U.S.** opportunities; NYC/North Jersey matches are ranked first.
- Supports **Greenhouse, Lever, Ashby, Workday**, plus a best-effort generic HTML careers-page scraper.
- Filters by any titles you specify.
- Filters by any keywords you specify.
- Can require **both a title match AND a keyword match**.
- Supports exclusions such as `Director` or `Vice President`.
- Remembers `first_seen` and marks newly discovered jobs as **NEW**.
- Automatically removes jobs from the live view when they disappear from the source on a later scan.
- Gives you a searchable, mobile-responsive live website.


## Your customized target list

The included `config.json` is already configured for these role families:

- Healthcare cloud engineering: Cloud Engineer, Cloud Infrastructure Engineer/Architect, Cloud Security Engineer, Cloud Architect.
- Clinical cloud delivery: Clinical DevOps Engineer, DevOps/DevSecOps Engineer, Platform Engineer, Site Reliability Engineer.
- Healthcare cybersecurity: Information Security Analyst, Cybersecurity Analyst/Engineer, Security Analyst/Engineer.
- Medical-device security: Medical Device Security, Product Security Engineer, Product Cybersecurity Engineer.
- HIPAA/GRC/audit: HIPAA Compliance Auditor, Security Compliance Analyst, IT Compliance Analyst, GRC Analyst, IT/Security Auditor.
- Incident response: Healthcare Incident Responder, Incident Response Analyst/Engineer, DFIR Analyst, Digital Forensics Analyst, SOC Analyst.

The included healthcare employers are UnitedHealth Group/Optum, The Cigna Group/Evernorth, Elevance Health, Centene, Humana, Kaiser Permanente, HCA Healthcare, Johnson & Johnson, McKesson, Cardinal Health, CVS Health/Aetna, Mayo Clinic, Cleveland Clinic, Abbott, Medtronic, GE HealthCare, Philips, Stryker, and Epic Systems.


## Location rules already configured

The app now uses this search policy:

1. **Priority 1 — NYC / North Jersey Metro:** New Jersey and New York City metro roles are accepted and ranked first. The configuration includes common hubs such as Jersey City, Newark, Hoboken, Parsippany, Morristown, Edison, Princeton, Manhattan, Brooklyn, Queens, the Bronx, White Plains, Stamford, and nearby areas.
2. **Priority 2 — U.S. Remote:** Fully remote roles are accepted across the United States.
3. **Excluded:** On-site/hybrid jobs outside the NYC/North Jersey metro and jobs whose stated location is explicitly outside the United States.

These rules are editable under `location_policy` in `config.json`.

## Daily email notification setup

The recipient is already configured as **`kingdomarmyknives@gmail.com`**. For security, the Gmail credential is **not** stored in the repository.

One-time setup in GitHub:

1. Turn on **2-Step Verification** for the Gmail account that will send the digest.
2. Create a Google **App Password** for the job watcher. Do **not** use your normal Gmail password.
3. In the GitHub repository, open **Settings → Secrets and variables → Actions → New repository secret**.
4. Name the secret exactly `GMAIL_APP_PASSWORD`.
5. Paste the 16-character Google App Password as the value and save it.
6. Go to **Actions → Daily job scan → Run workflow** once to test it.

After that, every scheduled run will scan the jobs and send the daily digest automatically. The email contains new-job counts, NYC/North Jersey matches, U.S.-remote matches, direct application links, and a warning if any company source failed that day.

## 1. Customize your searches

Edit `config.json`.

### Filters

```json
"filters": {
  "title_any": [
    "Cloud Engineer",
    "Cloud Security Engineer",
    "DevOps Engineer",
    "Information Security Analyst",
    "Medical Device Security",
    "GRC Analyst",
    "Incident Response Analyst"
  ],
  "keyword_any": [
    "HIPAA", "PHI", "EHR", "cloud", "AWS", "Azure",
    "cybersecurity", "incident response", "HITRUST", "IAM"
  ],
  "exclude_any": ["vice president"],
  "require_title_and_keyword": true
}
```

- `title_any`: the job title must contain at least one of these phrases.
- `keyword_any`: title, location, or description must contain at least one of these phrases.
- `exclude_any`: reject a posting if it contains one of these phrases.
- `require_title_and_keyword: true`: requires a title match **and** a keyword match.
- Set it to `false` to accept a title match **or** a keyword match.

### Companies

Enable only the companies you want by setting `"enabled": true`.

#### Greenhouse
If the careers URL resembles `https://boards.greenhouse.io/acme`, the board token is usually `acme`.

```json
{
  "name": "Acme",
  "type": "greenhouse",
  "board_token": "acme",
  "enabled": true
}
```

#### Lever
If the careers URL resembles `https://jobs.lever.co/acme`, use `acme` as the site name.

```json
{
  "name": "Acme",
  "type": "lever",
  "site": "acme",
  "enabled": true
}
```

#### Ashby
If the board is `https://jobs.ashbyhq.com/acme`, use `acme` as the board name.

```json
{
  "name": "Acme",
  "type": "ashby",
  "board_name": "acme",
  "enabled": true
}
```

#### Workday
Paste the company's public Workday careers URL.

```json
{
  "name": "Acme",
  "type": "workday",
  "careers_url": "https://acme.wd1.myworkdayjobs.com/en-US/External",
  "enabled": true
}
```

#### Generic company careers page
Use this when the site is mostly regular HTML. You can provide one page with `careers_url`, or several targeted technology/security pages with `careers_urls`.

```json
{
  "name": "Acme Health",
  "type": "generic",
  "careers_urls": [
    "https://www.acmehealth.com/careers/technology",
    "https://www.acmehealth.com/careers/cybersecurity"
  ],
  "enabled": true
}
```

The generic scraper prefilters visible job links using your target titles before opening detail pages, which keeps the daily scan lightweight. It is still best-effort: JavaScript-only listings, CAPTCHAs, login gates, or anti-bot protections may require a custom adapter.

## 2. Put it on GitHub

1. Create a new **public** GitHub repository, for example `daily-job-watcher`.
2. Upload the **contents inside this folder** to the repository so that `config.json`, `scraper.py`, `docs/`, and `.github/` appear at the repository root.
3. Open **Settings → Pages**.
4. Under **Build and deployment → Source**, choose **GitHub Actions**. Do not choose “Deploy from a branch” for this version.
5. Open **Settings → Secrets and variables → Actions** and add the `GMAIL_APP_PASSWORD` secret described above.
6. Open **Actions → Daily job scan → Run workflow** for the first scan and deployment.

After the workflow succeeds, GitHub Pages will give you a URL resembling:

`https://YOUR-USERNAME.github.io/daily-job-watcher/`

The same daily workflow now performs all four steps automatically: **scrape jobs → save results → deploy the refreshed dashboard → send the Gmail digest**.

## 3. Run the first scan immediately

Go to **Actions → Daily job scan → Run workflow**.

After the workflow finishes, open the live Pages URL. The workflow deploys the refreshed `docs/` dashboard automatically.

## 4. Change the daily time

The workflow currently runs at 7:17 AM in New York time:

```yaml
schedule:
  - cron: '17 7 * * *'
    timezone: 'America/New_York'
```

Edit `.github/workflows/daily-jobs.yml` to change it.

## Important notes

- Respect each employer's terms of use, `robots.txt`, and reasonable request rates.
- Prefer public ATS/job-board endpoints over aggressive HTML scraping.
- Never try to defeat CAPTCHAs, login gates, or anti-bot protections.
- Scheduled GitHub Actions run on the default branch. GitHub may disable scheduled workflows in a public repository after 60 days with no repository activity; re-enable the workflow if that happens.
- GitHub Pages is static hosting, which is ideal here because the scheduled scraper writes fresh `jobs.json` into the site.

## Local test

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python scraper.py
python -m http.server 8000 --directory docs
```

Open `http://localhost:8000`.

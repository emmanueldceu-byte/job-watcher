# Healthcare Cloud & Cybersecurity Job Watcher — Expanded Role-Level Edition

A $0 GitHub-hosted job watcher that checks selected healthcare and health-technology employers every day, classifies matching jobs by **role family + career level**, prioritizes **NYC/North Jersey** and **U.S. remote** roles, updates a live GitHub Pages dashboard, and emails a daily digest to `kingdomarmyknives@gmail.com`.

## What changed in this edition

The matcher no longer depends on a few exact titles such as `Cloud Engineer`. It now recognizes a broad set of related job titles and classifies them into these role families:

- Cloud & Infrastructure
- DevOps & Platform
- Security Operations & Engineering
- Incident Response & DFIR
- Identity, IAM & PAM
- GRC, Risk, Audit & Compliance
- Vulnerability & Endpoint Security
- Application, Product & Medical Device Security
- Network Security
- Data Security & Privacy Engineering
- Healthcare & Clinical Systems Security

It also assigns each match to a career level:

- Intern / New Grad
- Entry / Junior
- Associate / Level I
- Level II / Mid
- Standard / Unspecified
- Senior IC / Architect

Manager, Director, VP, Chief, Principal, Staff, Lead, Head-of and similar leadership titles are excluded by default. Senior individual-contributor and architect jobs are still included but rank below early-career and mid-level jobs. Jobs whose descriptions clearly require more than 7 years are excluded by default.

## Examples now recognized

Examples include Junior Cloud Support Engineer, Cloud Infrastructure Engineer II, Associate IAM Analyst, Cybersecurity Analyst I, Security Operations Analyst, SOC Analyst, GRC Analyst II, Third-Party Risk Analyst, Vulnerability Management Analyst, Endpoint Security Engineer, Application Security Analyst, Product Cybersecurity Engineer I, Medical Device Security Engineer, Network Security Analyst, Data Protection Analyst, EHR Security Analyst, Epic Security Analyst, and many title variants in those families.

## Ranking order

The dashboard and email sort matches primarily as follows:

1. NYC / North Jersey metro
2. U.S. remote
3. Within each location group: Intern/New Grad → Entry/Junior → Associate/Level I → Level II/Mid → Standard/Unspecified → Senior IC/Architect
4. Stronger title/keyword matches rank higher within the same group

## Dashboard filters

The live site now lets you filter by:

- Search text
- Company
- Role family
- Career level
- Location type
- New jobs only

Each job card shows its role family and career level.

## Companies included

UnitedHealth Group/Optum, The Cigna Group/Evernorth, Elevance Health, Centene, Humana, Kaiser Permanente, HCA Healthcare, Johnson & Johnson, McKesson, Cardinal Health, CVS Health/Aetna, Mayo Clinic, Cleveland Clinic, Abbott, Medtronic, GE HealthCare, Philips, Stryker, and Epic Systems.

## Location rules

The app accepts:

- NYC / North Jersey metro positions
- Fully remote U.S. positions

It rejects clearly non-U.S. roles and on-site/hybrid roles outside the preferred metro area.

## Daily email

The digest recipient is already set to `kingdomarmyknives@gmail.com`.

In GitHub, store the Gmail App Password as a repository Actions secret named exactly:

`GMAIL_APP_PASSWORD`

Do not put your normal Gmail password in the repository.

## Deploy or upgrade an existing repository

If you already deployed the earlier version, you do **not** need a new repository.

1. Unzip this package.
2. In your existing GitHub repository, replace these files/folders with the versions from this package:
   - `config.json`
   - `scraper.py`
   - `notify.py`
   - `docs/index.html`
   - `docs/app.js`
   - `.github/workflows/daily-jobs.yml`
   - optionally `README.md`
3. Commit the changes to `main`.
4. Go to **Actions → Daily job scan → Run workflow**.
5. Open the new run and confirm the steps are green.
6. Refresh your GitHub Pages site after deployment finishes.

The workflow uses the current Node-24-compatible Pages action majors:

- `actions/configure-pages@v6`
- `actions/upload-pages-artifact@v5`
- `actions/deploy-pages@v5`

## Adjusting the matching rules

The main settings are in `config.json`.

`role_families` contains the title variants accepted for each career area. Add another title phrase to the appropriate family if you want to broaden it further.

`exclude_title_any` contains leadership or unrelated titles to reject.

`max_required_years` is currently `7`. Lower this to focus more strongly on early-career jobs, or raise it to include more experienced positions.

`include_senior_ic` is currently `true`. Change it to `false` if you want the app to omit Senior Engineer/Senior Analyst/Architect-type individual-contributor roles entirely.

`require_keyword` is currently `false`. This is intentional: because every monitored employer is already healthcare/health-tech, a strong relevant job title can qualify without requiring the description to repeat a healthcare or cloud/security keyword.

## Daily schedule

The workflow is configured for 7:17 AM New York time:

```yaml
schedule:
  - cron: '17 7 * * *'
    timezone: 'America/New_York'
```

## Important limitation

The generic HTML adapter is best-effort. Some employers render job results almost entirely with JavaScript or use anti-bot systems, so a career page can expose fewer listings to a simple scheduled scraper than a human browser sees. The app also supports Greenhouse, Lever, Ashby, and Workday adapters when a company can be mapped to one of those public job systems.

## Local test

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python scraper.py
python -m http.server 8000 --directory docs
```

Then open `http://localhost:8000`.

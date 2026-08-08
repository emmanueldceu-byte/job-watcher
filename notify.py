from __future__ import annotations

import html
import json
import os
import smtplib
import sys
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
JOBS_PATH = ROOT / "docs" / "jobs.json"


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    note = config.get("notifications", {})
    if not note.get("daily_email", False):
        print("Daily email is disabled in config.json")
        return 0

    recipient = os.getenv("JOB_WATCHER_RECIPIENT") or note.get("recipient")
    sender = os.getenv("GMAIL_USERNAME") or recipient
    password = os.getenv("GMAIL_APP_PASSWORD")
    if not recipient or not sender:
        print("Email recipient/sender is not configured.", file=sys.stderr)
        return 1
    if not password:
        print("GMAIL_APP_PASSWORD is missing; skipping email.")
        return 0

    payload = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    jobs = payload.get("jobs", [])
    new_jobs = [j for j in jobs if j.get("is_new")]
    preferred = [j for j in jobs if j.get("location_priority") == 0]
    remote = [j for j in jobs if j.get("location_priority") == 1]
    errors = payload.get("errors", [])

    tz_name = note.get("timezone", "America/New_York")
    today = datetime.now(ZoneInfo(tz_name)).strftime("%b %d, %Y")
    subject = f"Job Watcher: {len(new_jobs)} new | {len(jobs)} matches — {today}"

    max_jobs = int(note.get("max_jobs_in_email", 30))
    display_jobs = sorted(
        jobs,
        key=lambda j: (j.get("location_priority", 99), not j.get("is_new", False), j.get("company", ""), j.get("title", "")),
    )[:max_jobs]

    rows = []
    for j in display_jobs:
        badge = "NEW · " if j.get("is_new") else ""
        category = j.get("location_category") or j.get("location") or "Location not listed"
        rows.append(
            f'''<tr>
              <td style="padding:14px 0;border-bottom:1px solid #e7eaf0;">
                <div style="font:700 16px Arial,sans-serif;color:#132238;">{esc(badge + j.get('title',''))}</div>
                <div style="margin-top:5px;font:14px Arial,sans-serif;color:#526173;">{esc(j.get('company',''))} · {esc(category)}</div>
                <div style="margin-top:5px;font:13px Arial,sans-serif;color:#687588;">{esc(j.get('location',''))}</div>
                <a href="{esc(j.get('url',''))}" style="display:inline-block;margin-top:9px;font:700 13px Arial,sans-serif;color:#2d5bff;text-decoration:none;">View &amp; apply →</a>
              </td>
            </tr>'''
        )

    jobs_html = "".join(rows) if rows else '<tr><td style="padding:18px 0;font:14px Arial,sans-serif;color:#526173;">No matching roles were found in today\'s scan.</td></tr>'

    error_html = ""
    if errors:
        names = ", ".join(esc(e.get("company", "Unknown")) for e in errors)
        error_html = f'<p style="font:12px Arial,sans-serif;color:#8a5a13;">Some sources could not be checked today: {names}.</p>'

    body = f'''<!doctype html>
<html><body style="margin:0;background:#f4f7fb;padding:24px;">
  <div style="max-width:720px;margin:auto;background:#ffffff;border:1px solid #e1e6ee;border-radius:18px;padding:26px;">
    <div style="font:700 12px Arial,sans-serif;color:#2d5bff;letter-spacing:.08em;">DAILY HEALTHCARE TECH JOB WATCHER</div>
    <h1 style="font:700 26px Arial,sans-serif;color:#122033;margin:8px 0 8px;">{len(new_jobs)} new job{'' if len(new_jobs)==1 else 's'} today</h1>
    <p style="font:14px/1.6 Arial,sans-serif;color:#526173;margin:0 0 8px;">{len(preferred)} NYC/North Jersey metro match{'' if len(preferred)==1 else 'es'} · {len(remote)} U.S. remote match{'' if len(remote)==1 else 'es'}.</p>
    <p style="font:13px/1.6 Arial,sans-serif;color:#687588;margin:0 0 18px;">NYC/North Jersey opportunities are ranked first, followed by fully remote U.S. opportunities.</p>
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0">{jobs_html}</table>
    {error_html}
    <p style="font:12px Arial,sans-serif;color:#8a94a4;margin-top:20px;">Showing up to {max_jobs} current matches. The live dashboard contains the full scan results.</p>
  </div>
</body></html>'''

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(
        f"Daily job watcher: {len(new_jobs)} new, {len(jobs)} current matches. "
        f"NYC/North Jersey: {len(preferred)}; US remote: {len(remote)}."
    )
    msg.add_alternative(body, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)

    print(f"Daily job digest sent to {recipient}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

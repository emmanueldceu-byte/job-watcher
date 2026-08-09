from __future__ import annotations

import hashlib
import gzip
import xml.etree.ElementTree as ET
from collections import deque
import html
import json
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
OUTPUT_PATH = ROOT / "docs" / "jobs.json"
STATE_PATH = ROOT / "data" / "state.json"

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (compatible; DailyJobWatcher/1.0; "
            "+https://github.com/)"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
)


@dataclass
class Job:
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    date_posted: str = ""
    source: str = ""
    first_seen: str = ""
    is_new: bool = False
    matched_titles: list[str] | None = None
    matched_keywords: list[str] | None = None
    role_family: str = ""
    seniority: str = ""
    seniority_priority: int = 99
    experience_years_min: int | None = None
    match_score: int = 0
    location_category: str = ""
    location_priority: int = 99

    @property
    def id(self) -> str:
        basis = f"{self.company}|{self.title}|{self.url}".lower().strip()
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:20]


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    value = BeautifulSoup(html.unescape(str(value)), "html.parser").get_text(" ")
    return re.sub(r"\s+", " ", value).strip()


def get_json(url: str, **kwargs):
    response = SESSION.get(url, timeout=30, **kwargs)
    response.raise_for_status()
    return response.json()


def fetch_greenhouse(company: dict) -> list[Job]:
    token = company["board_token"].strip()
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    payload = get_json(url)
    jobs = []
    for row in payload.get("jobs", []):
        jobs.append(
            Job(
                title=clean_text(row.get("title")),
                company=company["name"],
                location=clean_text((row.get("location") or {}).get("name")),
                url=row.get("absolute_url", ""),
                description=clean_text(row.get("content")),
                date_posted=row.get("updated_at", "") or "",
                source="Greenhouse",
            )
        )
    return jobs


def fetch_lever(company: dict) -> list[Job]:
    site = company["site"].strip()
    payload = get_json(f"https://api.lever.co/v0/postings/{site}?mode=json")
    jobs = []
    for row in payload:
        categories = row.get("categories") or {}
        description_parts = [row.get("descriptionPlain", "")]
        for item in row.get("lists", []) or []:
            description_parts.append(item.get("text", ""))
            description_parts.append(item.get("content", ""))
        jobs.append(
            Job(
                title=clean_text(row.get("text")),
                company=company["name"],
                location=clean_text(categories.get("location")),
                url=row.get("hostedUrl", "") or row.get("applyUrl", ""),
                description=clean_text(" ".join(description_parts)),
                source="Lever",
            )
        )
    return jobs


def fetch_ashby(company: dict) -> list[Job]:
    board = company["board_name"].strip()
    payload = get_json(f"https://api.ashbyhq.com/posting-api/job-board/{board}")
    jobs = []
    for row in payload.get("jobs", []):
        jobs.append(
            Job(
                title=clean_text(row.get("title")),
                company=company["name"],
                location=clean_text(row.get("location")),
                url=row.get("jobUrl", "") or row.get("applyUrl", ""),
                description=clean_text(row.get("descriptionPlain") or row.get("descriptionHtml")),
                date_posted=row.get("publishedAt", "") or "",
                source="Ashby",
            )
        )
    return jobs


def parse_workday_url(careers_url: str):
    parsed = urlparse(careers_url)
    host = parsed.netloc
    path = [p for p in parsed.path.split("/") if p]
    if not host or not path:
        raise ValueError("Workday URL must look like https://tenant.wd1.myworkdayjobs.com/en-US/SiteName")
    site = path[-1]
    tenant = host.split(".")[0]
    return parsed.scheme or "https", host, tenant, site


def fetch_workday(company: dict) -> list[Job]:
    careers_url = company["careers_url"].strip()
    scheme, host, tenant, site = parse_workday_url(careers_url)
    endpoint = f"{scheme}://{host}/wday/cxs/{tenant}/{site}/jobs"
    offset = 0
    limit = 20
    jobs = []
    while True:
        response = SESSION.post(
            endpoint,
            json={"appliedFacets": {}, "limit": limit, "offset": offset, "searchText": ""},
            timeout=30,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("jobPostings", []) or []
        if not rows:
            break
        for row in rows:
            external_path = row.get("externalPath", "")
            detail_url = urljoin(careers_url.rstrip("/") + "/", external_path.lstrip("/"))
            description = ""
            date_posted = row.get("postedOn", "") or ""
            # Workday list results often omit the full description. Fetch detail when possible.
            try:
                if external_path:
                    detail_endpoint = f"{scheme}://{host}/wday/cxs/{tenant}/{site}{external_path}"
                    detail = get_json(detail_endpoint)
                    info = detail.get("jobPostingInfo", {}) or {}
                    description = clean_text(info.get("jobDescription"))
                    detail_url = info.get("externalUrl") or detail_url
                    date_posted = info.get("startDate") or date_posted
            except Exception:
                pass
            jobs.append(
                Job(
                    title=clean_text(row.get("title")),
                    company=company["name"],
                    location=clean_text(row.get("locationsText")),
                    url=detail_url,
                    description=description,
                    date_posted=date_posted,
                    source="Workday",
                )
            )
        offset += len(rows)
        total = payload.get("total")
        if len(rows) < limit or (isinstance(total, int) and offset >= total):
            break
        time.sleep(0.25)
    return jobs


def looks_like_job_link(text: str, href: str) -> bool:
    hay = f"{text} {href}".lower()
    bad_terms = ("privacy", "cookie", "linkedin", "facebook", "instagram", "twitter", "login", "sign in", "talent community")
    if any(term in hay for term in bad_terms):
        return False
    path = urlparse(href).path.lower()
    strong = bool(re.search(r"/(?:job|jobs|position|positions|requisition|requisitions)/(?:[^/?#]+/){0,5}[^/?#]+", path))
    return strong or any(term in hay for term in ("job", "career", "position", "opening", "requisition", "vacancy", "role"))


def _same_host_or_subdomain(url: str, seed: str) -> bool:
    a = (urlparse(url).hostname or "").lower()
    b = (urlparse(seed).hostname or "").lower()
    if not a or not b:
        return False
    return a == b or a.endswith("." + b) or b.endswith("." + a)


def _is_listing_or_pagination_link(anchor, href: str, current_url: str) -> bool:
    if not _same_host_or_subdomain(href, current_url):
        return False
    text = clean_text(anchor.get_text(" ")).lower()
    rel = " ".join(anchor.get("rel") or []).lower()
    parsed = urlparse(href)
    q = parsed.query.lower()
    path = parsed.path.lower()
    if "next" in rel or text in {"next", "next page", ">", "›", "»"}:
        return True
    if re.fullmatch(r"\d{1,3}", text or ""):
        return True
    if re.search(r"(?:^|&)(?:page|from|start|offset)=\d+", q):
        return True
    if re.search(r"/page/\d+", path):
        return True
    if any(x in path for x in ("search-results", "search-jobs", "/jobs")) and any(x in q for x in ("page=", "from=", "start=", "offset=")):
        return True
    return False


def _discovery_hits(text: str, discovery_terms: list[str]) -> int:
    t = clean_text(text).lower()
    return sum(1 for term in discovery_terms if term.lower() in t)


def _candidate_score(text: str, href: str, discovery_terms: list[str]) -> int:
    path = urlparse(href).path.lower()
    score = 0
    if re.search(r"/(?:job|jobs)/(?:[^/?#]+/){0,5}(?:\d{4,}|[^/?#]{8,})", path):
        score += 12
    elif any(x in path for x in ("/job/", "/jobs/", "/position/", "/requisition/")):
        score += 7
    score += min(_discovery_hits(text, discovery_terms) * 8, 24)
    score += min(_discovery_hits(href.replace("-", " ").replace("_", " "), discovery_terms) * 6, 18)
    if any(x in path for x in ("search", "category", "teams", "career-areas")):
        score -= 6
    return score


def _iter_jsonld_objects(value):
    if isinstance(value, dict):
        yield value
        if "@graph" in value:
            yield from _iter_jsonld_objects(value["@graph"])
    elif isinstance(value, list):
        for item in value:
            yield from _iter_jsonld_objects(item)


def _location_from_jobposting(item: dict) -> str:
    job_type = str(item.get("jobLocationType") or "").lower()
    applicant = item.get("applicantLocationRequirements")
    applicant_text = clean_text(json.dumps(applicant, ensure_ascii=False)) if applicant else ""
    locations = item.get("jobLocation")
    if not isinstance(locations, list):
        locations = [locations] if locations else []
    found = []
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        addr = loc.get("address") or {}
        if isinstance(addr, dict):
            parts = [addr.get("addressLocality"), addr.get("addressRegion"), addr.get("addressCountry")]
            text = ", ".join(str(x) for x in parts if x)
            if text:
                found.append(text)
    if "telecommute" in job_type or "remote" in job_type:
        if re.search(r"\b(us|usa|united states|united states of america)\b", applicant_text, re.I):
            return "Remote, United States"
        return "Remote" + (f"; {'; '.join(found)}" if found else "")
    return "; ".join(found)


def _jobposting_from_soup(soup: BeautifulSoup, company: dict, fallback_url: str) -> Job | None:
    for node in soup.find_all("script", type="application/ld+json"):
        raw = node.string or node.get_text() or ""
        try:
            data = json.loads(raw)
        except Exception:
            continue
        for item in _iter_jsonld_objects(data):
            kind = item.get("@type")
            kinds = kind if isinstance(kind, list) else [kind]
            if "JobPosting" not in kinds:
                continue
            title = clean_text(item.get("title"))
            if not title:
                continue
            return Job(
                title=title,
                company=company["name"],
                location=_location_from_jobposting(item),
                url=clean_text(item.get("url")) or fallback_url,
                description=clean_text(item.get("description"))[:40000],
                date_posted=clean_text(item.get("datePosted")),
                source="Career site / JobPosting",
            )
    return None


def _parse_sitemap(content: bytes, url: str) -> tuple[str, list[str]]:
    try:
        if content[:2] == b"\x1f\x8b" or url.lower().endswith(".gz"):
            content = gzip.decompress(content)
    except Exception:
        pass
    root = ET.fromstring(content)
    tag = root.tag.rsplit("}", 1)[-1].lower()
    locs = [clean_text(el.text) for el in root.iter() if el.tag.rsplit("}", 1)[-1].lower() == "loc" and clean_text(el.text)]
    return tag, locs


def _discover_from_sitemaps(seed_url: str, discovery_terms: list[str], company: dict) -> dict[str, tuple[int, str]]:
    parsed = urlparse(seed_url)
    origin = f"{parsed.scheme or 'https'}://{parsed.netloc}"
    sitemap_queue = deque()
    seen_sitemaps = set()
    candidates: dict[str, tuple[int, str]] = {}

    try:
        r = SESSION.get(urljoin(origin, "/robots.txt"), timeout=12)
        if r.ok:
            for line in r.text.splitlines():
                if line.lower().startswith("sitemap:"):
                    sitemap_queue.append(line.split(":", 1)[1].strip())
    except Exception:
        pass
    for common in ("/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml"):
        sitemap_queue.append(urljoin(origin, common))

    max_sitemaps = 12
    max_urls = int(company.get("sitemap_url_limit", 3500))
    collected_joblike: list[tuple[str, int]] = []
    url_count = 0

    while sitemap_queue and len(seen_sitemaps) < max_sitemaps and url_count < max_urls:
        sm_url = sitemap_queue.popleft()
        if sm_url in seen_sitemaps:
            continue
        seen_sitemaps.add(sm_url)
        try:
            resp = SESSION.get(sm_url, timeout=15)
            if not resp.ok or not resp.content:
                continue
            tag, locs = _parse_sitemap(resp.content, sm_url)
        except Exception:
            continue
        if tag == "sitemapindex":
            for loc in locs[:50]:
                if loc not in seen_sitemaps:
                    sitemap_queue.append(loc)
            continue
        for loc in locs:
            url_count += 1
            if url_count > max_urls:
                break
            if not loc.startswith(("http://", "https://")):
                continue
            score = _candidate_score("", loc, discovery_terms)
            path = urlparse(loc).path.lower()
            is_joblike = any(x in path for x in ("/job/", "/jobs/", "/position/", "/requisition/"))
            if is_joblike:
                collected_joblike.append((loc, score))

    # When a sitemap is small, keep all job-like URLs; for huge sites, prefer URLs
    # whose slugs contain one of the user's technology/security discovery terms.
    soft_cap = int(company.get("candidate_limit", 350)) * 2
    for loc, score in collected_joblike:
        if len(collected_joblike) <= soft_cap or score >= 18:
            candidates[loc] = (score, "")
    return candidates


def _discover_from_listings(source_urls: list[str], discovery_terms: list[str], company: dict) -> dict[str, tuple[int, str]]:
    candidates: dict[str, tuple[int, str]] = {}
    page_limit = int(company.get("listing_page_limit", 12))
    queue = deque(source_urls)
    visited = set()

    while queue and len(visited) < page_limit * max(1, len(source_urls)):
        page_url = queue.popleft()
        if page_url in visited:
            continue
        visited.add(page_url)
        try:
            response = SESSION.get(page_url, timeout=25)
            response.raise_for_status()
            if "html" not in response.headers.get("content-type", "text/html").lower():
                continue
            soup = BeautifulSoup(response.text, "html.parser")
        except Exception:
            continue

        # Some search systems put one or more JobPosting objects directly in HTML.
        direct = _jobposting_from_soup(soup, company, page_url)
        if direct:
            candidates[direct.url] = (100, direct.title)

        for anchor in soup.find_all("a", href=True):
            href = urljoin(page_url, anchor.get("href"))
            text = clean_text(anchor.get_text(" ") or anchor.get("aria-label") or anchor.get("title"))
            if not href.startswith(("http://", "https://")):
                continue
            if _is_listing_or_pagination_link(anchor, href, page_url) and href not in visited:
                queue.append(href)
            if not looks_like_job_link(text, href):
                continue
            score = _candidate_score(text, href, discovery_terms)
            # A strong job-detail URL can be kept even when the visible text is just "View job".
            # Otherwise require a technology/security discovery signal in title or URL.
            if score < 12:
                continue
            old = candidates.get(href)
            if old is None or score > old[0]:
                candidates[href] = (score, text[:240])
    return candidates


def _fetch_job_detail(href: str, anchor_text: str, company: dict) -> Job | None:
    try:
        detail = SESSION.get(href, timeout=20)
        if not detail.ok or "html" not in detail.headers.get("content-type", "text/html").lower():
            return None
        soup = BeautifulSoup(detail.text, "html.parser")
        structured = _jobposting_from_soup(soup, company, href)
        if structured:
            return structured
        title = anchor_text
        h1 = soup.find("h1")
        if h1:
            title = clean_text(h1.get_text(" ")) or title
        if not title:
            title = clean_text((soup.find("title") or {}).get_text(" ") if soup.find("title") else "")
        page_text = clean_text(soup.get_text(" "))[:40000]
        location = ""
        # Common text patterns used when JobPosting JSON-LD is unavailable.
        for pattern in (
            r"(?:Primary location|Location|Locations)\s*[:\-]\s*([^|•]{2,120})",
            r"\b(Remote(?:\s*[-,]\s*(?:US|USA|United States|[A-Z]{2}))?)\b",
        ):
            m = re.search(pattern, page_text, re.I)
            if m:
                location = clean_text(m.group(1))
                break
        return Job(
            title=clean_text(title),
            company=company["name"],
            location=location,
            url=href,
            description=page_text,
            source="Career site",
        )
    except Exception:
        return None


def fetch_generic(company: dict, filters: dict | None = None) -> list[Job]:
    filters = filters or {}
    configured_urls = company.get("careers_urls") or [company.get("careers_url", "")]
    source_urls = [u.strip() for u in configured_urls if isinstance(u, str) and u.strip()]
    if not source_urls:
        raise ValueError("Generic company needs careers_url or careers_urls")

    discovery_terms = [x.strip() for x in filters.get("discovery_title_terms", []) if x.strip()]
    if not discovery_terms:
        role_families = filters.get("role_families", {}) or {}
        discovery_terms = [term for terms in role_families.values() for term in terms]

    candidates: dict[str, tuple[int, str]] = {}
    listing_candidates = _discover_from_listings(source_urls, discovery_terms, company)
    candidates.update(listing_candidates)

    if company.get("deep_discovery", True):
        for seed in source_urls:
            for href, value in _discover_from_sitemaps(seed, discovery_terms, company).items():
                old = candidates.get(href)
                if old is None or value[0] > old[0]:
                    candidates[href] = value

    ranked = sorted(candidates.items(), key=lambda kv: (-kv[1][0], kv[0]))
    detail_limit = int(company.get("detail_fetch_limit", company.get("candidate_limit", 350)))
    jobs: list[Job] = []
    seen_urls = set()
    for href, (_, anchor_text) in ranked[:detail_limit]:
        if href in seen_urls:
            continue
        seen_urls.add(href)
        job = _fetch_job_detail(href, anchor_text, company)
        if job and job.title:
            jobs.append(job)
        time.sleep(0.04)
    return jobs


def fetch_company(company: dict, filters: dict | None = None) -> list[Job]:
    kind = company.get("type", "generic").lower().strip()
    if kind == "greenhouse":
        return fetch_greenhouse(company)
    if kind == "lever":
        return fetch_lever(company)
    if kind == "ashby":
        return fetch_ashby(company)
    if kind == "workday":
        return fetch_workday(company)
    if kind == "generic":
        return fetch_generic(company, filters)
    raise ValueError(f"Unsupported company type: {kind}")


def term_matches(text: str, term: str) -> bool:
    # Phrase match, case-insensitive. Word boundaries for short/alphanumeric terms.
    text = text.lower()
    term = term.lower().strip()
    if not term:
        return False
    if len(term) <= 3 and term.isalnum():
        return re.search(rf"\b{re.escape(term)}\b", text) is not None
    return term in text


def classify_role_family(title: str, description: str, filters: dict) -> tuple[str, list[str]]:
    role_families = filters.get("role_families", {}) or {}
    best_family = ""
    best_terms: list[str] = []
    for family, terms in role_families.items():
        matches = [term for term in terms if term_matches(title, term)]
        if matches and (not best_terms or max(map(len, matches)) > max(map(len, best_terms))):
            best_family = family
            best_terms = matches
    if best_family:
        return best_family, best_terms

    # Many healthcare employers use generic titles such as "Technology Analyst II" or
    # "Enterprise Engagement Analyst". If the title is a plausible technical role and
    # the description contains strong cloud/security signals, classify by those signals.
    title_nouns = filters.get("generic_title_nouns", []) or []
    signal_map = filters.get("domain_signals", {}) or {}
    has_role_noun = any(term_matches(title, noun) for noun in title_nouns)
    has_title_domain_signal = any(term_matches(title, sig) for signals in signal_map.values() for sig in signals)
    if not has_role_noun and not has_title_domain_signal:
        return "", []
    if any(term_matches(title, x) for x in (filters.get("exclude_function_terms", []) or [])):
        return "", []
    all_text = f"{title} {description}"
    best_signal_family = ""
    best_signals: list[str] = []
    for family, signals in signal_map.items():
        matches = [sig for sig in signals if term_matches(all_text, sig)]
        if matches and (not best_signals or len(matches) > len(best_signals) or max(map(len, matches)) > max(map(len, best_signals))):
            best_signal_family = family
            best_signals = matches
    return best_signal_family, best_signals


def classify_seniority(title: str, filters: dict) -> tuple[str, int]:
    t = f" {title.lower()} "
    levels = (filters.get("seniority_policy", {}) or {}).get("levels", {}) or {}

    def pri(label: str, default: int) -> tuple[str, int]:
        return label, int(levels.get(label, default))

    if re.search(r"\b(intern|internship|co-op|coop|new grad|new graduate|graduate program|early career|apprentice)\b", t):
        return pri("Intern / New Grad", 0)
    if re.search(r"\b(entry[- ]level|junior|jr\.?|level 1|level one)\b", t):
        return pri("Entry / Junior", 1)
    if re.search(r"\b(associate|analyst i|analyst 1|engineer i|engineer 1|specialist i|specialist 1|administrator i|administrator 1|consultant i|consultant 1|technician i|technician 1)\b", t):
        return pri("Associate / Level I", 2)
    if re.search(r"\b(analyst ii|analyst 2|engineer ii|engineer 2|specialist ii|specialist 2|administrator ii|administrator 2|consultant ii|consultant 2|technician ii|technician 2|level 2|level two|intermediate|mid[- ]level)\b", t):
        return pri("Level II / Mid", 3)
    if re.search(r"\b(analyst iii|analyst 3|engineer iii|engineer 3|specialist iii|specialist 3|analyst iv|analyst 4|engineer iv|engineer 4|level 3|level three|level 4|level four)\b", t):
        return pri("Level III / IV", 4)
    if re.search(r"\b(lead|staff|principal|architect|distinguished|fellow)\b", t):
        return pri("Lead / Staff / Principal / Architect", 7)
    if re.search(r"\b(senior|sr\.?)\b", t):
        return pri("Senior IC", 6)
    return pri("Standard / Unspecified", 5)


def extract_min_years(description: str) -> int | None:
    text = clean_text(description).lower()
    patterns = [
        r"(?:minimum|min\.?|at least)\s+(\d{1,2})\+?\s+years",
        r"(\d{1,2})\+\s+years(?: of)? experience",
        r"(\d{1,2})\s*(?:-|to)\s*\d{1,2}\s+years(?: of)? experience",
    ]
    found: list[int] = []
    for pattern in patterns:
        for m in re.finditer(pattern, text):
            try:
                found.append(int(m.group(1)))
            except Exception:
                pass
    return min(found) if found else None


def filter_job(job: Job, filters: dict) -> bool:
    keyword_terms = [x.strip() for x in filters.get("keyword_any", []) if x.strip()]
    exclude_title_terms = [x.strip() for x in filters.get("exclude_title_any", []) if x.strip()]

    title_text = clean_text(job.title)
    all_text = f"{job.title} {job.location} {job.description}"

    if any(term_matches(title_text, x) for x in exclude_title_terms):
        return False

    role_family, matched_titles = classify_role_family(title_text, job.description, filters)
    matched_keywords = [x for x in keyword_terms if term_matches(all_text, x)]
    seniority, seniority_priority = classify_seniority(title_text, filters)
    min_years = extract_min_years(job.description)

    policy = filters.get("seniority_policy", {}) or {}
    if seniority == "Lead / Staff / Principal / Architect" and not policy.get("include_advanced_ic", True):
        return False

    max_required_years = filters.get("max_required_years")
    if isinstance(max_required_years, int) and min_years is not None and min_years > max_required_years:
        return False

    if filters.get("require_role_family", True) and not role_family:
        return False
    if filters.get("require_keyword", False) and keyword_terms and not matched_keywords:
        return False

    job.matched_titles = matched_titles
    job.matched_keywords = matched_keywords
    job.role_family = role_family or "Other Relevant Technology"
    job.seniority = seniority
    job.seniority_priority = seniority_priority
    job.experience_years_min = min_years

    score = 58 + min(len(matched_titles) * 7, 28) + min(len(matched_keywords) * 2, 16)
    score += max(0, 12 - seniority_priority)
    if min_years is not None and min_years <= 3:
        score += 8
    job.match_score = min(score, 100)
    return True


def _term_in(text: str, term: str) -> bool:
    """Location-aware term matching; 2-letter state codes use token boundaries."""
    text_l = text.lower()
    term_l = term.lower().strip()
    if not term_l:
        return False
    if len(term_l) == 2 and term_l.isalpha():
        return re.search(rf"(?<![a-z]){re.escape(term_l)}(?![a-z])", text_l) is not None
    return term_l in text_l


def location_allowed(job: Job, policy: dict) -> bool:
    """Accept NYC/North-Jersey metro roles or remote roles intended for the U.S."""
    if not policy:
        return True

    location = clean_text(job.location)
    all_text = clean_text(f"{job.title} {job.location} {job.description}")

    metro_terms = policy.get("metro_terms", [])
    remote_terms = policy.get("remote_terms", ["remote"])
    us_terms = policy.get("us_terms", ["United States", "USA", "U.S."])
    non_us_terms = policy.get("non_us_terms", [])

    metro_match = any(_term_in(location, x) for x in metro_terms)
    remote_location = any(_term_in(location, x) for x in remote_terms)
    remote_anywhere = any(_term_in(all_text, x) for x in remote_terms)
    us_anywhere = any(_term_in(all_text, x) for x in us_terms)
    non_us_location = any(_term_in(location, x) for x in non_us_terms)

    if metro_match and policy.get("allow_nyc_nj_metro", True):
        job.location_category = policy.get("preferred_label", "NYC / North Jersey Metro")
        job.location_priority = 0
        return True

    if policy.get("allow_us_remote", True):
        # U.S. career sites often label U.S.-remote postings simply as "Remote".
        # Explicitly non-U.S. locations are rejected. Description-only remote
        # matches must also include an explicit U.S. signal.
        remote_us = (remote_location and not non_us_location) or (remote_anywhere and us_anywhere)
        if remote_us:
            job.location_category = policy.get("remote_label", "US Remote")
            job.location_priority = 1
            return True

    if policy.get("us_only", True):
        return False

    job.location_category = "Other"
    job.location_priority = 2
    return True

def load_state() -> dict:
    if not STATE_PATH.exists():
        return {"seen": {}}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"seen": {}}


def save_results(jobs: Iterable[Job], app_name: str, errors: list[dict], scan_stats: list[dict] | None = None):
    now = datetime.now(timezone.utc).isoformat()
    state = load_state()
    seen = state.setdefault("seen", {})

    serialized = []
    for job in jobs:
        first_seen = seen.get(job.id)
        if not first_seen:
            first_seen = now
            seen[job.id] = first_seen
            job.is_new = True
        job.first_seen = first_seen
        row = asdict(job)
        row["id"] = job.id
        row["description"] = clean_text(row["description"])[:1200]
        serialized.append(row)

    serialized.sort(key=lambda x: (
        x.get("location_priority", 99),
        x.get("seniority_priority", 99),
        -x.get("match_score", 0),
        not x["is_new"],
        x["company"].lower(),
        x["title"].lower(),
    ))
    payload = {
        "app_name": app_name,
        "updated_at": now,
        "count": len(serialized),
        "errors": errors,
        "scan_stats": scan_stats or [],
        "jobs": serialized,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    companies = [c for c in config.get("companies", []) if c.get("enabled", True)]
    filters = config.get("filters", {})
    errors: list[dict] = []
    scan_stats: list[dict] = []
    matches: dict[str, Job] = {}

    for company in companies:
        try:
            postings = fetch_company(company, filters)
            role_count = 0
            location_count = 0
            for job in postings:
                if not (job.title and job.url):
                    continue
                if not filter_job(job, filters):
                    continue
                role_count += 1
                if not location_allowed(job, config.get("location_policy", {})):
                    continue
                location_count += 1
                matches[job.id] = job
            stat = {"company": company["name"], "fetched": len(postings), "role_matches": role_count, "location_matches": location_count}
            scan_stats.append(stat)
            print(f"{company['name']}: fetched {len(postings)} | relevant {role_count} | NYC/NJ or US-remote {location_count}")
        except Exception as exc:
            print(f"ERROR {company.get('name')}: {exc}", file=sys.stderr)
            errors.append({"company": company.get("name", "Unknown"), "error": str(exc)[:300]})
            scan_stats.append({"company": company.get("name", "Unknown"), "fetched": 0, "role_matches": 0, "location_matches": 0, "error": str(exc)[:160]})

    save_results(matches.values(), config.get("app_name", "Daily Job Watcher"), errors, scan_stats)
    print(f"Saved {len(matches)} matching jobs to {OUTPUT_PATH}")
    return 0 if not errors else 0  # One company failing should not block all updates.


if __name__ == "__main__":
    raise SystemExit(main())

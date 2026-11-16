"""LinkedIn public job search (no login).

We run a few broad searches for India, last N seconds, entry/intern/associate
level, newest first. Then we keep only companies from the list.
"""
import html
import re
import time

from ..common import get, strip_html

SEARCH = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{}"

QUERIES = [
    "software OR developer OR SDE OR programmer OR \"full stack\" OR backend OR frontend",
    "\"data scientist\" OR \"data analyst\" OR \"data engineer\" OR analytics OR \"business analyst\"",
    "\"machine learning\" OR AI OR \"artificial intelligence\" OR \"deep learning\" OR NLP OR LLM OR GenAI OR \"computer vision\"",
    "intern OR internship OR trainee OR graduate OR fresher OR \"new grad\" OR \"early career\"",
    "engineer OR \"systems engineer\" OR \"associate engineer\" OR cloud OR devops OR QA OR security",
]

_CARD_SPLIT = re.compile(r"<li[ >]")
_ID = re.compile(r"urn:li:jobPosting:(\d+)")
_TITLE = re.compile(r'base-search-card__title">\s*(.*?)\s*</h3>', re.S)
_COMP = re.compile(r'base-search-card__subtitle">(.*?)</h4>', re.S)
_LOC = re.compile(r'job-search-card__location">\s*(.*?)\s*</span>', re.S)
_TIME = re.compile(r'<time[^>]*datetime="([^"]*)"[^>]*>\s*(.*?)\s*</time>', re.S)
_DESC = re.compile(r'show-more-less-html__markup[^>]*>(.*?)</div>', re.S)
_CRIT = re.compile(r'description__job-criteria-subheader">\s*(.*?)\s*</h3>\s*<span[^>]*>\s*(.*?)\s*</span>', re.S)


def _parse_cards(page: str):
    out = []
    for chunk in _CARD_SPLIT.split(page)[1:]:
        m = _ID.search(chunk)
        t = _TITLE.search(chunk)
        if not (m and t):
            continue
        c = _COMP.search(chunk)
        loc = _LOC.search(chunk)
        tm = _TIME.search(chunk)
        out.append({
            "id": m.group(1),
            "title": html.unescape(strip_html(t.group(1))),
            "company": html.unescape(strip_html(c.group(1))) if c else "",
            "location": html.unescape(strip_html(loc.group(1))) if loc else "",
            "posted": (tm.group(2).strip() if tm else ""),
            "date": (tm.group(1) if tm else ""),
        })
    return out


def search(window_sec: int, seen_ids: set, log, max_pages: int = 20, levels: str = "1,2,3"):
    """Yield raw LinkedIn cards for all queries. Stops paging early when a page has
    nothing new (results are newest first)."""
    got = {}
    for q in QUERIES:
        empty_new = 0
        for page in range(max_pages):
            params = {
                "keywords": q, "location": "India", "geoId": "102713980",
                "f_TPR": f"r{window_sec}", "f_E": levels, "sortBy": "DD",
                "start": page * 25,
            }
            try:
                r = get(SEARCH, params=params)
            except Exception as e:  # network error: move to next query
                log(f"linkedin: {e.__class__.__name__} on page {page}")
                break
            if r.status_code != 200:
                log(f"linkedin: HTTP {r.status_code} on page {page}")
                break
            cards = _parse_cards(r.text)
            if not cards:
                break
            new = 0
            for c in cards:
                if c["id"] not in got:
                    got[c["id"]] = c
                    if f"li:{c['id']}" not in seen_ids:
                        new += 1
            empty_new = empty_new + 1 if new == 0 else 0
            if empty_new >= 2:
                break
            time.sleep(1.2)
        time.sleep(1.5)
    return list(got.values())


def detail(job_id: str):
    """Return (description_text, criteria dict). Empty on failure."""
    try:
        r = get(DETAIL.format(job_id))
        if r.status_code != 200:
            return "", {}
        m = _DESC.search(r.text)
        desc = strip_html(m.group(1)) if m else ""
        crit = {strip_html(a): strip_html(b) for a, b in _CRIT.findall(r.text)}
        return desc, crit
    except Exception:
        return "", {}


def job_url(job_id: str) -> str:
    return f"https://www.linkedin.com/jobs/view/{job_id}/"

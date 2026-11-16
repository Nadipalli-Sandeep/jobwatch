"""Readers for company career sites (applicant tracking systems).

Every reader returns a list of dicts:
  {id, title, location, url, posted, country?, desc?}
`desc` may be missing; then `details(src, job)` can fetch it later (only for new jobs).
"""
import json
import re
import time
from urllib.parse import quote, urlparse

from ..common import get, post, strip_html
from ..filters import is_india

# ---------------------------------------------------------------- Greenhouse
def greenhouse(src):
    slug = src["slug"]
    r = get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", params={"content": "true"})
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        offices = " ".join(o.get("name", "") + " " + (o.get("location") or "") for o in j.get("offices", []) or [])
        if not is_india(loc + " " + offices):
            continue
        out.append({"id": str(j["id"]), "title": j.get("title", ""), "location": loc,
                    "url": j.get("absolute_url", ""), "posted": (j.get("first_published") or j.get("updated_at") or "")[:10],
                    "desc": strip_html(j.get("content", ""))})
    return out


# ---------------------------------------------------------------- Lever
def lever(src):
    host = "api.eu.lever.co" if src.get("eu") else "api.lever.co"
    r = get(f"https://{host}/v0/postings/{src['slug']}", params={"mode": "json"})
    r.raise_for_status()
    out = []
    for j in r.json():
        cat = j.get("categories") or {}
        locs = " ".join([cat.get("location") or ""] + (cat.get("allLocations") or []))
        if not is_india(locs, j.get("country", "")):
            continue
        desc = j.get("descriptionPlain", "") + " " + " ".join(
            strip_html(x.get("content", "")) for x in j.get("lists", []) or [])
        ts = j.get("createdAt")
        out.append({"id": j["id"], "title": j.get("text", ""), "location": cat.get("location", ""),
                    "url": j.get("hostedUrl", ""),
                    "posted": time.strftime("%Y-%m-%d", time.gmtime(ts / 1000)) if ts else "",
                    "desc": desc})
    return out


# ---------------------------------------------------------------- Ashby
def ashby(src):
    r = get(f"https://api.ashbyhq.com/posting-api/job-board/{src['slug']}")
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j.get("location") or ""] + [s.get("location", "") for s in j.get("secondaryLocations", []) or []]
        country = (((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry") or "")
        if not is_india(" ".join(locs), country):
            continue
        out.append({"id": j.get("id", j.get("jobUrl")), "title": j.get("title", ""),
                    "location": j.get("location", ""), "url": j.get("jobUrl", ""),
                    "posted": (j.get("publishedAt") or "")[:10], "desc": j.get("descriptionPlain", "")})
    return out


# ---------------------------------------------------------------- SmartRecruiters
def smartrecruiters(src):
    slug = src["slug"]
    out, offset = [], 0
    while True:
        r = get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
                params={"country": "in", "limit": 100, "offset": offset})
        r.raise_for_status()
        data = r.json()
        for j in data.get("content", []):
            loc = j.get("location") or {}
            out.append({"id": j["id"], "title": j.get("name", ""),
                        "location": ", ".join(x for x in [loc.get("city"), loc.get("region"), "India"] if x),
                        "url": f"https://jobs.smartrecruiters.com/{slug}/{j['id']}",
                        "posted": (j.get("releasedDate") or "")[:10], "ref": j.get("ref", "")})
        offset += 100
        if offset >= data.get("totalFound", 0) or offset >= 1000:
            break
    return out


def _sr_detail(src, job):
    r = get(job["ref"])
    if r.status_code != 200:
        return ""
    secs = (r.json().get("jobAd") or {}).get("sections") or {}
    return " ".join(strip_html((secs.get(k) or {}).get("text", "")) for k in
                    ("jobDescription", "qualifications", "additionalInformation"))


# ---------------------------------------------------------------- Workday
def _find_india_facet(facets):
    """Workday facets can be nested. Return (facetParameter, id) for 'India'."""
    for f in facets or []:
        param = f.get("facetParameter")
        for v in f.get("values", []) or []:
            if "values" in v and isinstance(v.get("values"), list):
                hit = _find_india_facet([{"facetParameter": v.get("facetParameter", param),
                                          "values": v["values"]}])
                if hit:
                    return hit
            if (v.get("descriptor") or "").strip().lower() == "india" and v.get("id"):
                return param, v["id"]
    return None


def workday(src):
    """src: {host: 'nvidia.wd5.myworkdayjobs.com', tenant: 'nvidia', site: 'NVIDIAExternalCareerSite'}"""
    base = f"https://{src['host']}"
    api = f"{base}/wday/cxs/{src['tenant']}/{src['site']}/jobs"
    hdr = {"Content-Type": "application/json", "Accept": "application/json"}
    body = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}
    r = post(api, data=json.dumps(body), headers=hdr)
    r.raise_for_status()
    first = r.json()
    facet = _find_india_facet(first.get("facets"))
    if facet:
        body["appliedFacets"] = {facet[0]: [facet[1]]}
    else:
        body["searchText"] = "India"
    out, offset, total = [], 0, None
    max_jobs = src.get("max", 600)
    while True:
        body["offset"] = offset
        r = post(api, data=json.dumps(body), headers=hdr)
        if r.status_code != 200:
            break
        data = r.json()
        if total is None:
            total = data.get("total", 0)
        posts = data.get("jobPostings", []) or []
        for j in posts:
            path = j.get("externalPath", "")
            loc = j.get("locationsText", "")
            if not facet and not is_india(loc + " " + path):
                continue
            out.append({"id": path.rsplit("_", 1)[-1] if "_" in path else path,
                        "title": j.get("title", ""), "location": loc,
                        "url": f"{base}/{src['site']}{path}", "posted": j.get("postedOn", ""),
                        "path": path})
        offset += 20
        if not posts or offset >= min(total or 0, max_jobs):
            break
        time.sleep(0.4)       # Workday rate-limits fast readers (shared Cloudflare)
    return out


def _wd_detail(src, job):
    r = get(f"https://{src['host']}/wday/cxs/{src['tenant']}/{src['site']}{job['path']}",
            headers={"Accept": "application/json"})
    if r.status_code != 200:
        return ""
    info = r.json().get("jobPostingInfo") or {}
    return strip_html(info.get("jobDescription", ""))


# ---------------------------------------------------------------- Eightfold (PCSX + old apply/v2)
def eightfold(src):
    """src: {host: 'apply.careers.microsoft.com', domain: 'microsoft.com', api: 'pcsx'|'v2'}"""
    host, domain = src["host"], src["domain"]
    out, start = [], 0
    max_jobs = src.get("max", 500)
    while start < max_jobs:
        if src.get("api", "pcsx") == "pcsx":
            r = get(f"https://{host}/api/pcsx/search",
                    params={"domain": domain, "query": "", "location": "India",
                            "start": start, "sort_by": "timestamp"})
            if r.status_code != 200:
                break
            data = (r.json().get("data") or {})
            pos = data.get("positions", []) or []
            for p in pos:
                locs = p.get("standardizedLocations") or p.get("locations") or []
                ts = p.get("postedTs")
                url = p.get("positionUrl") or f"/careers/job/{p['id']}"
                out.append({"id": str(p["id"]), "title": p.get("name", ""),
                            "location": "; ".join(locs[:3]),
                            "url": url if url.startswith("http") else f"https://{host}{url}",
                            "posted": time.strftime("%Y-%m-%d", time.gmtime(ts)) if ts else ""})
        else:
            r = get(f"https://{host}/api/apply/v2/jobs",
                    params={"domain": domain, "location": "India", "start": start,
                            "num": 10, "sort_by": "timestamp"})
            if r.status_code != 200:
                break
            pos = r.json().get("positions", []) or []
            for p in pos:
                ts = p.get("t_create")
                out.append({"id": str(p["id"]), "title": p.get("name", ""),
                            "location": p.get("location", ""),
                            "url": p.get("canonicalPositionUrl") or f"https://{host}/careers/job/{p['id']}",
                            "posted": time.strftime("%Y-%m-%d", time.gmtime(ts)) if ts else "",
                            "desc": strip_html(p.get("job_description", ""))})
        if not pos:
            break
        start += len(pos)
    return [j for j in out if is_india(j["location"]) or src.get("trust_location")]


def _ef_detail(src, job):
    if src.get("api", "pcsx") != "pcsx":
        return job.get("desc", "")
    r = get(f"https://{src['host']}/api/pcsx/position_details",
            params={"position_id": job["id"], "domain": src["domain"]})
    if r.status_code != 200:
        return ""
    d = r.json().get("data") or {}
    return strip_html(d.get("jobDescription", ""))


# ---------------------------------------------------------------- Oracle HCM Cloud
def oracle(src):
    """src: {host: 'jpmc.fa.oraclecloud.com', site: 'CX_1001'}"""
    host, site = src["host"], src["site"]
    out, offset = [], 0
    while offset < src.get("max", 500):
        finder = (f"findReqs;siteNumber={site},limit=100,offset={offset},"
                  f"sortBy=POSTING_DATES_DESC,locationId={src['location_id']}" if src.get("location_id")
                  else f"findReqs;siteNumber={site},limit=100,offset={offset},sortBy=POSTING_DATES_DESC,keyword=India")
        r = get(f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions",
                params={"onlyData": "true", "expand": "requisitionList.secondaryLocations",
                        "finder": finder})
        if r.status_code != 200:
            break
        items = r.json().get("items", [])
        reqs = items[0].get("requisitionList", []) if items else []
        for j in reqs:
            locs = (j.get("PrimaryLocation") or "") + " " + " ".join(
                s.get("Name", "") for s in j.get("secondaryLocations", []) or [])
            if not is_india(locs, j.get("PrimaryLocationCountry", "")):
                continue
            out.append({"id": str(j["Id"]), "title": j.get("Title", ""),
                        "location": j.get("PrimaryLocation", ""),
                        "url": f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{j['Id']}",
                        "posted": (j.get("PostedDate") or "")[:10],
                        "desc": strip_html((j.get("ShortDescriptionStr") or ""))})
        if len(reqs) < 100:
            break
        offset += 100
    return out


def _oracle_detail(src, job):
    r = get(f"https://{src['host']}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails",
            params={"expand": "all", "onlyData": "true",
                    "finder": f'ById;Id="{job["id"]}",siteNumber={src["site"]}'})
    if r.status_code != 200:
        return job.get("desc", "")
    items = r.json().get("items", [])
    if not items:
        return job.get("desc", "")
    it = items[0]
    return strip_html(" ".join(it.get(k) or "" for k in
                               ("ExternalDescriptionStr", "ExternalQualificationsStr", "ExternalResponsibilitiesStr")))


# ---------------------------------------------------------------- Amazon
def amazon(src):
    out, offset = [], 0
    while offset < src.get("max", 1000):
        r = get("https://www.amazon.jobs/en/search.json",
                params={"country": "IND", "sort": "recent", "result_limit": 100, "offset": offset})
        if r.status_code != 200:
            break
        jobs = r.json().get("jobs", [])
        for j in jobs:
            out.append({"id": str(j.get("id_icims") or j.get("id")), "title": j.get("title", ""),
                        "location": j.get("normalized_location") or j.get("location", ""),
                        "url": "https://www.amazon.jobs" + j.get("job_path", ""),
                        "posted": j.get("posted_date", ""),
                        "desc": strip_html(" ".join([j.get("basic_qualifications") or "",
                                                     j.get("preferred_qualifications") or "",
                                                     j.get("description") or ""]))})
        if len(jobs) < 100:
            break
        offset += 100
    return out


# ---------------------------------------------------------------- registry
READERS = {
    "greenhouse": greenhouse, "lever": lever, "ashby": ashby,
    "smartrecruiters": smartrecruiters, "workday": workday,
    "eightfold": eightfold, "oracle": oracle, "amazon": amazon,
}

DETAILS = {
    "smartrecruiters": _sr_detail, "workday": _wd_detail,
    "eightfold": _ef_detail, "oracle": _oracle_detail,
}


def fetch(src):
    return READERS[src["type"]](src)


def details(src, job):
    if job.get("desc"):
        return job["desc"]
    fn = DETAILS.get(src["type"])
    try:
        return fn(src, job) if fn else ""
    except Exception:
        return ""

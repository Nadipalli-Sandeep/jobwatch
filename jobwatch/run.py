"""One check cycle: read all sources, find new matching jobs, send alerts.

  py -3.12 -m jobwatch.run            # normal
  DRY_RUN=1 py -3.12 -m jobwatch.run  # print alerts, send nothing

State (which jobs were already seen) lives in $STATE_DIR (default ./state).
"""
import json
import os
import re
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

from . import notify
from .common import IST, now_ist
from .companies import DATA, CompanyMatcher, norm
from .filters import classify, title_ok
from .sources import ats, linkedin

STATE_DIR = Path(os.environ.get("STATE_DIR", "state"))
LI_WINDOW = int(os.environ.get("LI_WINDOW", "3600"))      # seconds of LinkedIn history per run
LI_DETAIL_CAP = int(os.environ.get("LI_DETAIL_CAP", "80"))
KEEP_DAYS = 45
HEARTBEAT_HOUR_IST = 9

_RANK = {"INTERNSHIP": 0, "FRESHER": 0, "0-1 YRS": 1, "ENTRY LEVEL": 2, "EXP NOT STATED": 3}


def log(msg):
    print(f"[{now_ist():%H:%M:%S}] {msg}", flush=True)


# ------------------------------------------------------------------ state
def load(name, default):
    p = STATE_DIR / name
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            log(f"state file {name} unreadable; starting it fresh")
    return default


def save(name, obj):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_DIR / (name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(STATE_DIR / name)


def short_name(line):
    s = re.sub(r"\s*\(.*?\)", "", line)
    s = re.sub(r"\s+India$", "", s).strip()
    return s or line


def source_key(src):
    return f"{src['type']}:{src.get('slug') or src.get('site') or src.get('host') or src['company']}"


# ------------------------------------------------------------------ main
def main():
    t0 = time.time()
    first_run = not (STATE_DIR / "seen.json").exists()
    seen = load("seen.json", {})              # uid -> unix time first seen
    titles = load("titles.json", {})          # company|title -> unix time alerted (cross-source dedupe)
    meta = load("meta.json", {})
    pending = load("pending.json", [])        # alerts that failed to send last time
    seeded = set(meta.get("seeded_sources", []))
    now = time.time()
    today = now_ist().strftime("%Y-%m-%d")
    if meta.get("day") != today:
        if meta.get("day"):
            meta["yesterday"] = meta.get("stats", {})
        meta["day"], meta["stats"] = today, {"runs": 0, "scanned": 0, "alerts": 0, "errors": {}}
    stats = meta["stats"]
    stats["runs"] += 1

    matcher = CompanyMatcher()
    sources = json.loads((DATA / "sources.json").read_text(encoding="utf-8")) if (DATA / "sources.json").exists() else []
    candidates = []        # (job dict, src or None)
    new_seen = {}

    # ---- 1. LinkedIn
    li_seen = {k for k in seen if k.startswith("li:")}
    try:
        cards = linkedin.search(LI_WINDOW, li_seen, log)
    except Exception as e:
        cards = []
        stats["errors"]["linkedin"] = stats["errors"].get("linkedin", 0) + 1
        log(f"linkedin failed: {e}")
    stats["scanned"] += len(cards)
    li_in_list = 0
    for c in cards:
        uid = f"li:{c['id']}"
        if uid in seen:
            continue
        line = matcher.match(c["company"])
        new_seen[uid] = now
        if not line:
            continue
        li_in_list += 1
        if not title_ok(c["title"])[0]:
            continue
        candidates.append(({"uid": uid, "company": line, "title": c["title"], "location": c["location"],
                            "url": linkedin.job_url(c["id"]), "posted": c["posted"], "source": "LinkedIn",
                            "li_id": c["id"]}, None))
    log(f"linkedin: {len(cards)} jobs, {li_in_list} new from your companies")

    # ---- 2. Company career sites
    def run_src(src):
        try:
            return src, ats.fetch(src), None
        except Exception as e:
            return src, [], f"{e.__class__.__name__}: {str(e)[:120]}"

    with ThreadPoolExecutor(12) as ex:
        results = list(ex.map(run_src, sources))
    newly_seeded = []
    for src, jobs, err in results:
        key = source_key(src)
        if err:
            stats["errors"][key] = stats["errors"].get(key, 0) + 1
            log(f"  {key}: {err}")
            continue
        stats["scanned"] += len(jobs)
        silent = key not in seeded          # brand-new source: remember its jobs, do not alert
        for j in jobs:
            uid = f"{src['type']}:{src['company']}:{j['id']}"
            if uid in seen:
                continue
            new_seen[uid] = now
            if silent or not title_ok(j["title"])[0]:
                continue
            candidates.append(({"uid": uid, "company": src["company"], "title": j["title"],
                                "location": j.get("location", ""), "url": j["url"],
                                "posted": j.get("posted", ""), "source": "Careers page",
                                "_raw": j}, src))
        if silent and jobs:
            newly_seeded.append(key)
    seeded.update(newly_seeded)
    if newly_seeded:
        log(f"new career sources remembered silently: {len(newly_seeded)}")
    log(f"career sites: {len(sources)} sources, {sum(len(r[1]) for r in results)} India jobs read")

    # ---- 3. Check experience (only for new jobs that passed the title check)
    alerts = []
    if first_run:
        log(f"first run: remembering {len(new_seen)} current jobs, no alerts")
        candidates = []

    def check(item):
        job, src = item
        if src is None:   # LinkedIn
            desc, crit = linkedin.detail(job["li_id"])
            level = (crit.get("Seniority level") or "").lower()
            hint = level in ("entry level", "internship", "not applicable", "")
            if "mid-senior" in level or "director" in level or "executive" in level:
                keep, tag, yrs = classify(job["title"], desc, False)
                if tag in ("EXP NOT STATED", "ENTRY LEVEL"):
                    keep = False
            else:
                keep, tag, yrs = classify(job["title"], desc, hint)
            time.sleep(0.8)
        else:
            desc = ats.details(src, job["_raw"])
            keep, tag, yrs = classify(job["title"], desc, False)
        return job, keep, tag, yrs

    li_items = [c for c in candidates if c[1] is None]
    ats_items = [c for c in candidates if c[1] is not None]
    checked = []
    for item in li_items[:LI_DETAIL_CAP]:
        checked.append(check(item))
    for job, _ in li_items[LI_DETAIL_CAP:]:       # too many this run: judge by title only
        keep, tag, yrs = classify(job["title"], "", True)
        checked.append((job, keep, tag, yrs))
    with ThreadPoolExecutor(8) as ex:
        checked.extend(ex.map(check, ats_items))

    for job, keep, tag, yrs in checked:
        if not keep:
            continue
        key = f"{norm(job['company'])}|{norm(job['title'])}"
        if titles.get(key, 0) > now - 3 * 86400:
            continue          # same job already sent from another site in the last 3 days
        titles[key] = now
        job.pop("_raw", None)
        job.pop("li_id", None)
        job.update(tag=tag, years=yrs, company_short=short_name(job["company"]))
        alerts.append(job)

    # retry alerts that failed last time (max 1 day old)
    pending = [p for p in pending if p.get("_t", now) > now - 86400]
    alerts = pending + alerts
    alerts.sort(key=lambda j: (_RANK.get(j["tag"], 9), j["company_short"]))
    log(f"alerts to send: {len(alerts)}")
    for a in alerts:
        log(f"  [{a['tag']}] {a['company_short']} | {a['title']} | {a['location']} | {a['url']}")

    # ---- 4. Send
    if alerts:
        if notify.send_jobs(alerts):
            stats["alerts"] += len(alerts)
            pending = []
        else:
            for a in alerts:
                a.setdefault("_t", now)
            pending = alerts
            log("could not deliver; will retry next run")
    else:
        pending = []

    if first_run:
        notify.send_note(
            "*JobWatch is ON*\n"
            f"Watching {len(matcher.lines)} companies: LinkedIn + {len(sources)} company career sites.\n"
            "You will get a message only when a NEW fresher / intern / 0-1 yr IT, software, data or AI job "
            "appears in India.\nA short daily status comes every morning at 9 AM.")

    # ---- 5. Daily heartbeat (so you know it is alive)
    hb_due = now_ist().hour >= HEARTBEAT_HOUR_IST and meta.get("heartbeat") != today
    if hb_due and not first_run:
        y = meta.get("yesterday", {})
        errs = sorted(stats["errors"].items(), key=lambda kv: -kv[1])[:5]
        text = (f"*JobWatch daily status* ({today})\n"
                f"Yesterday: {y.get('runs', 0)} checks, {y.get('scanned', 0)} job listings read, "
                f"{y.get('alerts', 0)} alerts sent.\n"
                f"Today so far: {stats['runs']} checks, {stats['alerts']} alerts.\n"
                + ("Sources with errors today: " + ", ".join(f"{k} ({v})" for k, v in errs) if errs
                   else "All sources OK."))
        if notify.send_note(text):
            meta["heartbeat"] = today

    # ---- 6. Save
    seen.update(new_seen)
    cutoff = now - KEEP_DAYS * 86400
    seen = {k: v for k, v in seen.items() if v > cutoff}
    titles = {k: v for k, v in titles.items() if v > now - 7 * 86400}
    meta["seeded_sources"] = sorted(seeded)
    meta["last_run"] = now_ist().isoformat(timespec="seconds")
    save("seen.json", seen)
    save("titles.json", titles)
    save("pending.json", pending)
    save("meta.json", meta)
    log(f"done in {time.time() - t0:.0f}s, remembering {len(seen)} jobs")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)

"""Shared helpers: HTTP session, text cleanup, IST time."""
import html
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

IST = timezone(timedelta(hours=5, minutes=30))
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")


def now_ist() -> datetime:
    return datetime.now(IST)


def make_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=1.5,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset(["GET", "POST"]),
                  respect_retry_after_header=True)
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    return s


SESSION = make_session()


def get(url, **kw):
    kw.setdefault("timeout", 30)
    return SESSION.get(url, **kw)


def post(url, **kw):
    kw.setdefault("timeout", 30)
    return SESSION.post(url, **kw)


_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = _TAG.sub(" ", text)
    text = html.unescape(text)  # some feeds double-escape
    return re.sub(r"\s+", " ", text).strip()


def ascii_fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def polite_sleep(sec: float):
    time.sleep(sec)

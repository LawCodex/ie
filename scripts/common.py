"""Shared helpers: polite HTTP client with on-disk cache, paths."""
import os
import threading
import time

import requests

ISB = "https://www.irishstatutebook.ie"
LRC = "https://revisedacts.lawreform.ie"
UA = "LawCodex/1.0 (+https://github.com/LawCodex)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.environ.get("LAWCODEX_RAW", os.path.join(os.path.dirname(ROOT), "_raw", "ie"))

# Minimum seconds between the start of two requests per host (neither site sets a Crawl-delay).
MIN_INTERVAL = float(os.environ.get("LAWCODEX_MIN_INTERVAL", "0.25"))

_lock = threading.Lock()
_last = {}
_local = threading.local()


def _session():
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        s.headers["User-Agent"] = UA
        _local.s = s
    return s


def _throttle(host):
    while True:
        with _lock:
            now = time.monotonic()
            wait = _last.get(host, 0) + MIN_INTERVAL - now
            if wait <= 0:
                _last[host] = now
                return
        time.sleep(wait)


def get(url, timeout=120, tries=8):
    """GET with per-host rate limiting and exponential backoff. Returns bytes, or None for 404."""
    host = url.split("/")[2]
    delay = 5
    err = None
    for _ in range(tries):
        _throttle(host)
        try:
            r = _session().get(url, timeout=timeout)
        except requests.RequestException as e:
            err = str(e)
        else:
            if r.status_code == 200:
                return r.content
            if r.status_code in (404, 410):
                return None
            err = f"HTTP {r.status_code}"
        time.sleep(delay)
        delay = min(delay * 2, 300)
    raise RuntimeError(f"{url}: {err}")


def cached(url, path):
    """Return content of url, cached at RAW/path. A cached 404 is stored as an empty '.404' marker."""
    full = os.path.join(RAW, path)
    if os.path.exists(full):
        with open(full, "rb") as f:
            return f.read()
    if os.path.exists(full + ".404"):
        return None
    os.makedirs(os.path.dirname(full), exist_ok=True)
    data = get(url)
    if data is None:
        open(full + ".404", "w").close()
        return None
    tmp = full + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, full)
    return data

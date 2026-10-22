#!/usr/bin/env python3
"""
Trump vs. Clinton front-page coverage, May 8 - Nov 7 2016.

For every day in the window, and for every newspaper in PAPERS, fetch the
Wayback Machine snapshot of the paper's homepage nearest to SNAPSHOT_HOUR_UTC,
extract the headlines, and record whether Donald Trump / Hillary Clinton are
mentioned in

  * the "top stories"  - the first TOP_N headlines in page order, and
  * any headline on the homepage.

Everything is cached on disk, so the script is resumable: kill it at any time
and re-run it; finished (paper, day) pairs are skipped.

Usage:
  python3 coverage.py run   [--start 2016-05-08 --end 2016-11-07] [--papers nyt,wapo] [--workers 3]
  python3 coverage.py reparse     # re-extract headlines from cached HTML (after parser changes)
  python3 coverage.py report      # rebuild daily CSV + summary from parsed results
  python3 coverage.py status      # progress counters
"""
import argparse
import datetime as dt
import gzip
import json
import logging
import random
import re
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RAW = DATA / "raw"            # gzipped homepage HTML, one per paper/day
PARSED = DATA / "parsed"      # one JSON per paper/day
ERRORS = DATA / "errors.jsonl"
LOG = DATA / "run.log"

ELECTION_DAY = dt.date(2016, 11, 8)
DEFAULT_START = dt.date(2016, 5, 8)
DEFAULT_END = dt.date(2016, 11, 7)
SNAPSHOT_HOUR_UTC = 14        # ~10am Eastern: morning edition is up
MAX_SNAPSHOT_DRIFT = dt.timedelta(hours=12)
TOP_N = 10
USER_AGENT = "trump-clinton-coverage-research/1.0 (academic; low rate)"

# Major US newspapers (by circulation / national prominence in 2016).
PAPERS = {
    "nyt":      ("The New York Times",            "nytimes.com"),
    "wapo":     ("The Washington Post",           "washingtonpost.com"),
    "wsj":      ("The Wall Street Journal",       "wsj.com"),
    "usatoday": ("USA Today",                     "usatoday.com"),
    "latimes":  ("Los Angeles Times",             "latimes.com"),
    "nypost":   ("New York Post",                 "nypost.com"),
    "nydn":     ("New York Daily News",           "nydailynews.com"),
    "chitrib":  ("Chicago Tribune",               "chicagotribune.com"),
    "bostonglobe": ("The Boston Globe",           "bostonglobe.com"),
    "sfchron":  ("San Francisco Chronicle",       "sfchronicle.com"),
    "houchron": ("Houston Chronicle",             "houstonchronicle.com"),
    "dallas":   ("The Dallas Morning News",       "dallasnews.com"),
    "philly":   ("The Philadelphia Inquirer",     "philly.com"),
    "newsday":  ("Newsday",                       "newsday.com"),
    "startrib": ("Star Tribune (Minneapolis)",    "startribune.com"),
    "denver":   ("The Denver Post",               "denverpost.com"),
    "ajc":      ("Atlanta Journal-Constitution",  "ajc.com"),
    "seattle":  ("The Seattle Times",             "seattletimes.com"),
    "miami":    ("Miami Herald",                  "miamiherald.com"),
    "tampa":    ("Tampa Bay Times",               "tampabay.com"),
}

# --- mention detection -------------------------------------------------------
# Case-sensitive, so the verb "trump" doesn't count. Family members are
# excluded so that only the candidates themselves count.
TRUMP_RE = re.compile(r"(?<!Melania )(?<!Ivanka )(?<!Eric )(?<!Tiffany )(?<!Barron )(?<!Lara )\bTrump(?:'s|’s)?\b")
CLINTON_RE = re.compile(r"\bHillary\b|(?<!Bill )(?<!Chelsea )\bClinton(?:'s|’s)?\b|\bHRC\b")
TRUMP_JR_RE = re.compile(r"\bTrump,? Jr\b|Donald Trump Jr")


def mentions_trump(text):
    return bool(TRUMP_RE.search(TRUMP_JR_RE.sub("", text)))


def mentions_clinton(text):
    return bool(CLINTON_RE.search(text))


# --- headline extraction -----------------------------------------------------
HEADLINE_CLASS_RE = re.compile(r"(headline|hed\b|story-heading|title|promo-?title)", re.I)
NAV_ANCESTOR_RE = re.compile(r"(nav|menu|footer|masthead|header-|site-header|ribbon|ticker|market|weather|trending|most-?popular|most-?read|newsletter|subscribe|sponsor|ad-|advert)", re.I)
MIN_WORDS = 4


def _in_chrome(el):
    """True if the element sits inside navigation / footer / sidebars."""
    for anc in el.parents:
        if anc.name in ("nav", "footer", "aside"):
            return True
        if anc.name in ("header",) and anc.find_parent("article") is None:
            return True
        attrs = " ".join(anc.get("class", []) or []) + " " + (anc.get("id") or "")
        if attrs.strip() and NAV_ANCESTOR_RE.search(attrs):
            return True
    return False


def extract_headlines(html):
    """Return headline strings in document order (deduplicated)."""
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript", "template", "svg"]):
        t.decompose()
    # Wayback injects its toolbar; strip it if present.
    for t in soup.select("#wm-ipp-base, #wm-ipp, #donato"):
        t.decompose()

    candidates = []
    for el in soup.find_all(True):
        is_h = el.name in ("h1", "h2", "h3", "h4")
        cls = " ".join(el.get("class", []) or [])
        is_cls = bool(cls and HEADLINE_CLASS_RE.search(cls)) and el.name in ("a", "div", "span", "p", "h5")
        if not (is_h or is_cls):
            continue
        # Skip containers that themselves hold other headline elements.
        if el.find(["h1", "h2", "h3", "h4"]):
            continue
        text = " ".join(el.get_text(" ", strip=True).split())
        if len(text.split()) < MIN_WORDS or len(text) > 250:
            continue
        if _in_chrome(el):
            continue
        candidates.append(text)

    seen, out = set(), []
    for t in candidates:
        k = t.lower()
        if k in seen:
            continue
        # drop strings that are a substring of an already-kept headline (nested markup)
        if any(k in s for s in seen):
            continue
        seen.add(k)
        out.append(t)
    return out


# --- Wayback fetching ---------------------------------------------------------
_local = threading.local()
_rate_lock = threading.Lock()
_last_req = [0.0]
_pause_until = [0.0]       # global circuit breaker: all threads wait while the archive is unreachable
_outage = {"since": None, "delay": 60}
MAX_OUTAGE_DELAY = 1800    # longest single wait while the archive is down

# Adaptive politeness: the gap between requests (shared by all threads) doubles on
# every rate-limit / dropped connection and shrinks 10% after each 20 clean requests,
# never below MIN_INTERVAL. It settles at whatever pace the archive tolerates.
MIN_INTERVAL = 6.0
MAX_INTERVAL = 120.0
_interval = [MIN_INTERVAL]
_clean = [0]


def _slow_down(reason):
    with _rate_lock:
        old = _interval[0]
        _interval[0] = min(old * 2, MAX_INTERVAL)
        _clean[0] = 0
    if _interval[0] != old:
        logging.warning("slowing down (%s): request gap %.0fs -> %.0fs", reason, old, _interval[0])


def _speed_up():
    with _rate_lock:
        _clean[0] += 1
        if _clean[0] >= 20 and _interval[0] > MIN_INTERVAL:
            _interval[0] = max(_interval[0] * 0.9, MIN_INTERVAL)
            _clean[0] = 0
            logging.info("speeding up: request gap now %.1fs", _interval[0])


def _session():
    if not hasattr(_local, "s"):
        s = requests.Session()
        s.headers["User-Agent"] = USER_AGENT
        _local.s = s
    return _local.s


def _throttle():
    while True:
        with _rate_lock:
            now = time.monotonic()
            gap = _interval[0] * random.uniform(0.8, 1.3)
            wait = max(_last_req[0] + gap, _pause_until[0]) - now
            if wait <= 0:
                _last_req[0] = now
                return
        time.sleep(min(wait, 30))


def _network_down(url, err):
    """Connection-level failure: pause everyone, back off, never give up."""
    with _rate_lock:
        now = time.monotonic()
        if _pause_until[0] > now:      # another thread already opened the breaker
            return
        if _outage["since"] is None:
            _outage["since"] = dt.datetime.utcnow()
            _outage["delay"] = 60
        else:
            _outage["delay"] = min(_outage["delay"] * 2, MAX_OUTAGE_DELAY)
        _pause_until[0] = now + _outage["delay"]
        logging.warning("ARCHIVE DOWN since %s (%s); pausing all workers %ds",
                        _outage["since"].isoformat(timespec="seconds"), err[:120], _outage["delay"])


def _network_up():
    with _rate_lock:
        if _outage["since"] is not None:
            logging.warning("ARCHIVE BACK after outage since %s", _outage["since"].isoformat(timespec="seconds"))
            _outage["since"] = None


class FetchError(Exception):
    pass


def http_get(url, tries=6, timeout=60):
    """HTTP errors are retried `tries` times; connection errors are retried forever."""
    delay = 10
    last = None
    attempt = 0
    while attempt < tries:
        _throttle()
        try:
            r = _session().get(url, timeout=timeout, allow_redirects=True)
        except requests.RequestException as e:
            _local.__dict__.pop("s", None)   # fresh connection pool next time
            _slow_down(type(e).__name__)
            _network_down(url, f"{type(e).__name__}: {e}")
            continue
        _network_up()
        if r.status_code == 200:
            _speed_up()
            return r
        if r.status_code == 404:
            raise FetchError(f"404 {url}")
        attempt += 1
        last = f"HTTP {r.status_code}"
        if r.status_code in (429, 503):
            _slow_down(f"HTTP {r.status_code}")
            with _rate_lock:
                _pause_until[0] = max(_pause_until[0], time.monotonic() + 120 * attempt)
            logging.warning("%s from archive; pausing all workers %ds", r.status_code, 120 * attempt)
        else:
            time.sleep(delay + random.random() * 2)
            delay = min(delay * 2, 300)
    raise FetchError(f"gave up after {tries} tries ({last}) {url}")


def find_snapshot(domain, day):
    """Return (timestamp, url) of the snapshot closest to the target time, or None.

    Uses the availability API on archive.org (more reliably reachable than the CDX server).
    """
    target = dt.datetime(day.year, day.month, day.day, SNAPSHOT_HOUR_UTC)
    url = (f"https://archive.org/wayback/available?url={domain}"
           f"&timestamp={target.strftime('%Y%m%d%H%M%S')}")
    closest = http_get(url).json().get("archived_snapshots", {}).get("closest")
    if not closest or not closest.get("available") or closest.get("status") != "200":
        return None
    ts = closest["timestamp"]
    if abs(dt.datetime.strptime(ts, "%Y%m%d%H%M%S") - target) > MAX_SNAPSHOT_DRIFT:
        return None
    orig = closest["url"].split(f"/web/{ts}/", 1)[1]
    return ts, orig


def fetch_html(ts, orig):
    # id_ => raw archived bytes without the Wayback toolbar / URL rewriting
    r = http_get(f"https://web.archive.org/web/{ts}id_/{orig}")
    r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else r.apparent_encoding
    return r.text


# --- per-item pipeline --------------------------------------------------------
def raw_path(key, day):
    return RAW / key / f"{day.isoformat()}.html.gz"


def parsed_path(key, day):
    return PARSED / key / f"{day.isoformat()}.json"


def log_error(key, day, msg):
    with _rate_lock:
        with open(ERRORS, "a") as f:
            f.write(json.dumps({"paper": key, "date": day.isoformat(), "error": msg,
                                "at": dt.datetime.utcnow().isoformat(timespec="seconds")}) + "\n")


def analyse(key, day, html, ts):
    heads = extract_headlines(html)
    top = heads[:TOP_N]
    rec = {
        "paper": key,
        "date": day.isoformat(),
        "snapshot": ts,
        "n_headlines": len(heads),
        "top": top,
        "top_trump": any(mentions_trump(h) for h in top),
        "top_clinton": any(mentions_clinton(h) for h in top),
        "top_trump_count": sum(mentions_trump(h) for h in top),
        "top_clinton_count": sum(mentions_clinton(h) for h in top),
        "any_trump": any(mentions_trump(h) for h in heads),
        "any_clinton": any(mentions_clinton(h) for h in heads),
        "all_trump_count": sum(mentions_trump(h) for h in heads),
        "all_clinton_count": sum(mentions_clinton(h) for h in heads),
    }
    # too few headlines means the extractor failed on this layout; flag it
    rec["usable"] = len(heads) >= TOP_N
    return rec


def process(key, day):
    pp = parsed_path(key, day)
    if pp.exists():
        return "skip"
    rp = raw_path(key, day)
    meta = rp.with_suffix("").with_suffix(".meta.json")
    try:
        if rp.exists() and meta.exists():
            html = gzip.decompress(rp.read_bytes()).decode("utf-8", "replace")
            ts = json.loads(meta.read_text())["snapshot"]
        else:
            snap = find_snapshot(PAPERS[key][1], day)
            if snap is None:
                pp.parent.mkdir(parents=True, exist_ok=True)
                pp.write_text(json.dumps({"paper": key, "date": day.isoformat(),
                                          "snapshot": None, "usable": False,
                                          "reason": "no snapshot within window"}))
                return "nosnap"
            ts, orig = snap
            html = fetch_html(ts, orig)
            rp.parent.mkdir(parents=True, exist_ok=True)
            rp.write_bytes(gzip.compress(html.encode("utf-8")))
            meta.write_text(json.dumps({"snapshot": ts, "original": orig}))
        rec = analyse(key, day, html, ts)
        pp.parent.mkdir(parents=True, exist_ok=True)
        pp.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        return "ok" if rec["usable"] else "unusable"
    except Exception as e:  # noqa: BLE001 - every failure is logged and retried on the next run
        log_error(key, day, f"{type(e).__name__}: {e}")
        return "error"


def daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += dt.timedelta(days=1)


# --- commands ----------------------------------------------------------------
def cmd_run(args):
    papers = args.papers.split(",") if args.papers else list(PAPERS)
    days = list(daterange(args.start, args.end))
    jobs = [(k, d) for d in days for k in papers]
    todo = [(k, d) for k, d in jobs if not parsed_path(k, d).exists()]
    logging.info("run: %d papers x %d days = %d items, %d to do", len(papers), len(days), len(jobs), len(todo))
    counts = defaultdict(int)
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(process, k, d): (k, d) for k, d in todo}
        for i, f in enumerate(as_completed(futs), 1):
            k, d = futs[f]
            res = f.result()
            counts[res] += 1
            if res != "ok":
                logging.info("%s %s -> %s", k, d, res)
            if i % 25 == 0 or i == len(todo):
                rate = i / (time.time() - t0)
                eta = (len(todo) - i) / rate / 60 if rate else 0
                logging.info("PROGRESS %d/%d %s  %.2f items/s  ETA %.0f min",
                             i, len(todo), dict(counts), rate, eta)
    cmd_report(args)
    logging.info("DONE %s", dict(counts))


def cmd_reparse(args):
    n = 0
    for meta in RAW.glob("*/*.meta.json"):
        key = meta.parent.name
        day = dt.date.fromisoformat(meta.name.split(".")[0])
        html = gzip.decompress(raw_path(key, day).read_bytes()).decode("utf-8", "replace")
        rec = analyse(key, day, html, json.loads(meta.read_text())["snapshot"])
        parsed_path(key, day).parent.mkdir(parents=True, exist_ok=True)
        parsed_path(key, day).write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        n += 1
    logging.info("reparsed %d snapshots", n)
    cmd_report(args)


def load_parsed():
    out = []
    for p in sorted(PARSED.glob("*/*.json")):
        out.append(json.loads(p.read_text()))
    return out


def cmd_report(args):
    recs = [r for r in load_parsed() if r.get("usable")]
    by_day = defaultdict(list)
    for r in recs:
        by_day[r["date"]].append(r)

    def pct(rows, field):
        return round(100 * sum(r[field] for r in rows) / len(rows), 1) if rows else ""

    lines = ["date,papers_checked,pct_top_trump,pct_top_clinton,pct_any_trump,pct_any_clinton,"
             "top_trump_headlines,top_clinton_headlines"]
    for day in sorted(by_day):
        rows = by_day[day]
        lines.append(",".join(str(x) for x in [
            day, len(rows), pct(rows, "top_trump"), pct(rows, "top_clinton"),
            pct(rows, "any_trump"), pct(rows, "any_clinton"),
            sum(r["top_trump_count"] for r in rows), sum(r["top_clinton_count"] for r in rows)]))
    (ROOT / "results_daily.csv").write_text("\n".join(lines) + "\n")

    # per-paper + overall summary
    by_paper = defaultdict(list)
    for r in recs:
        by_paper[r["paper"]].append(r)
    summ = ["# Trump vs. Clinton on US newspaper homepages", "",
            f"Window: {DEFAULT_START} - {DEFAULT_END} (election day {ELECTION_DAY}). "
            f"Top stories = first {TOP_N} homepage headlines; snapshot nearest {SNAPSHOT_HOUR_UTC}:00 UTC.", ""]
    if recs:
        days_pct = [(pct(v, "top_trump"), pct(v, "top_clinton")) for v in by_day.values()]
        t_mean = sum(a for a, _ in days_pct) / len(days_pct)
        c_mean = sum(b for _, b in days_pct) / len(days_pct)
        t_wins = sum(a > b for a, b in days_pct)
        c_wins = sum(b > a for a, b in days_pct)
        summ += [f"- Usable paper-days: {len(recs)} across {len(by_day)} days",
                 f"- Mean daily % of papers with Trump in top stories: **{t_mean:.1f}%**",
                 f"- Mean daily % of papers with Clinton in top stories: **{c_mean:.1f}%**",
                 f"- Days Trump % > Clinton %: {t_wins}; Clinton > Trump: {c_wins}; ties: {len(days_pct) - t_wins - c_wins}",
                 "", "| paper | days | % days Trump in top | % days Clinton in top |", "|---|---|---|---|"]
        for k in sorted(by_paper):
            v = by_paper[k]
            summ.append(f"| {PAPERS[k][0]} | {len(v)} | {pct(v, 'top_trump')} | {pct(v, 'top_clinton')} |")
    (ROOT / "results_summary.md").write_text("\n".join(summ) + "\n")
    logging.info("report written: %d usable paper-days, %d days", len(recs), len(by_day))


def cmd_status(args):
    papers = list(PAPERS)
    days = list(daterange(DEFAULT_START, DEFAULT_END))
    recs = load_parsed()
    usable = sum(1 for r in recs if r.get("usable"))
    nosnap = sum(1 for r in recs if r.get("snapshot") is None)
    errs = sum(1 for _ in open(ERRORS)) if ERRORS.exists() else 0
    print(f"done {len(recs)}/{len(papers) * len(days)}  usable {usable}  no-snapshot {nosnap}  "
          f"unusable {len(recs) - usable - nosnap}  error-log lines {errs}")
    per = defaultdict(lambda: [0, 0])
    for r in recs:
        per[r["paper"]][0] += 1
        per[r["paper"]][1] += bool(r.get("usable"))
    for k in papers:
        print(f"  {k:12s} done {per[k][0]:4d}  usable {per[k][1]:4d}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "reparse", "report", "status"])
    ap.add_argument("--start", type=dt.date.fromisoformat, default=DEFAULT_START)
    ap.add_argument("--end", type=dt.date.fromisoformat, default=DEFAULT_END)
    ap.add_argument("--papers")
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(LOG), logging.StreamHandler(sys.stdout)])
    {"run": cmd_run, "reparse": cmd_reparse, "report": cmd_report, "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    main()

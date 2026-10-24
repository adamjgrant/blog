#!/usr/bin/env python3
"""Trump vs. Biden/Harris on news homepages, May 5 - Nov 4, 2024.

Source: GDELT Global Frontpage Graph (GFG), which records every link on
~50,000 news homepages each hour, with its link text and its order on the
page. For each day we take the 14:00 UTC (10am ET) file, falling back to
nearby hours for sites missing from it, and keep only our publications.

Commands:
  fetch   download/filter the hourly files (resumable)
  report  score every homepage and write the daily CSV + summary
"""
import argparse, csv, datetime as dt, gzip, io, json, os, re, subprocess, sys, time
from collections import defaultdict
from urllib.parse import urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "data", "raw")
URL = "https://data.gdeltproject.org/gdeltv3/gfg/alpha/{}.LINKS.TXT.gz"
START, END = dt.date(2024, 5, 5), dt.date(2024, 11, 4)
SWITCH = dt.date(2024, 7, 22)          # Harris is the candidate from this date's snapshot on
HOURS = ["14", "15", "13", "16", "12"]  # preference order (UTC)
TOP_N = 10                              # "top stories" = first N headlines on the page

# homepage key (host + path, no www/port/trailing slash) -> display name
SITES = {
    "nytimes.com": "New York Times", "latimes.com": "Los Angeles Times",
    "chicagotribune.com": "Chicago Tribune", "bostonglobe.com": "Boston Globe",
    "nypost.com": "New York Post", "inquirer.com": "Philadelphia Inquirer",
    "dallasnews.com": "Dallas Morning News", "denverpost.com": "Denver Post",
    "ajc.com": "Atlanta Journal-Constitution", "startribune.com": "Star Tribune",
    "tampabay.com": "Tampa Bay Times", "stltoday.com": "St. Louis Post-Dispatch",
    "oregonlive.com": "The Oregonian", "cleveland.com": "Cleveland Plain Dealer",
    "nj.com": "NJ.com (Star-Ledger)", "post-gazette.com": "Pittsburgh Post-Gazette",
    "baltimoresun.com": "Baltimore Sun", "mercurynews.com": "San Jose Mercury News",
    "ocregister.com": "Orange County Register",
    "sandiegouniontribune.com": "San Diego Union-Tribune",
    "orlandosentinel.com": "Orlando Sentinel", "sun-sentinel.com": "South Florida Sun Sentinel",
    "reviewjournal.com": "Las Vegas Review-Journal", "spokesman.com": "Spokesman-Review",
    "newsday.com": "Newsday", "washingtontimes.com": "Washington Times",
    "csmonitor.com": "Christian Science Monitor",
    "cnn.com": "CNN", "foxnews.com": "Fox News", "nbcnews.com": "NBC News",
    "abcnews.go.com": "ABC News", "cbsnews.com": "CBS News", "msnbc.com": "MSNBC",
    "npr.org": "NPR", "thehill.com": "The Hill", "newsweek.com": "Newsweek",
    "time.com": "Time", "huffpost.com": "HuffPost", "slate.com": "Slate",
    "vox.com": "Vox", "breitbart.com": "Breitbart", "drudgereport.com": "Drudge Report",
    "washingtonexaminer.com": "Washington Examiner",
    "theguardian.com/us": "The Guardian (US)",
    "dailymail.co.uk/ushome/index.html": "Daily Mail (US)", "bbc.com": "BBC",
}


def key_of(url):
    p = urlparse(url)
    host = (p.hostname or "").removeprefix("www.")
    return (host + p.path).rstrip("/")


def days():
    d = START
    while d <= END:
        yield d
        d += dt.timedelta(days=1)


def stream_hour(stamp, want):
    """Stream one hourly file; return {site: [(order, text, to_url)]} for sites in want.
    A site crawled twice in the hour keeps only its first crawl."""
    out, done = {}, set()
    cur = None
    for attempt in range(6):
        try:
            p = subprocess.Popen(f"curl -sSf --retry 3 '{URL.format(stamp)}' | gunzip -c",
                                 shell=True, stdout=subprocess.PIPE)
            out, done, cur = {}, set(), None
            for raw in io.TextIOWrapper(p.stdout, encoding="utf-8", errors="replace"):
                f = raw.rstrip("\n").split("\t")
                if len(f) < 5:
                    continue
                k = key_of(f[1])
                if k != cur:
                    if cur in out:
                        done.add(cur)
                    cur = k
                if k not in want or k in done:
                    continue
                out.setdefault(k, []).append((int(f[2]), f[5] if len(f) > 5 else "", f[4]))
            if p.wait() == 0:
                return out
            if p.returncode == 1:   # gunzip ok but curl 404 -> empty
                pass
        except Exception as e:
            print("  error", stamp, e, file=sys.stderr)
        time.sleep(10 * (attempt + 1))
    print("  giving up on", stamp, file=sys.stderr)
    return {}


def cmd_fetch(args):
    os.makedirs(RAW, exist_ok=True)
    chronic = set()   # sites missing all of the previous day: only look for them in the first hour
    for d in days():
        path = os.path.join(RAW, d.strftime("%Y%m%d") + ".json.gz")
        if os.path.exists(path):
            with gzip.open(path, "rt") as fh:
                chronic = set(SITES) - set(json.load(fh))
            continue
        t0 = time.time()
        got = {}
        for i, h in enumerate(HOURS):
            missing = set(SITES) - set(got) - (chronic if i else set())
            if not missing:
                break
            res = stream_hour(d.strftime("%Y%m%d") + h + "0000", missing)
            for k, rows in res.items():
                got[k] = {"hour": h, "links": sorted(rows)}
        with gzip.open(path + ".tmp", "wt") as fh:
            json.dump(got, fh)
        os.replace(path + ".tmp", path)
        chronic = set(SITES) - set(got)
        print(f"{d} sites={len(got)}/{len(SITES)} missing={sorted(set(SITES)-set(got))} "
              f"{time.time()-t0:.0f}s", flush=True)
    print("FETCH DONE", flush=True)


# ---------------------------------------------------------------- scoring
TRUMP = re.compile(r"\btrump(?:'s|’s)?\b", re.I)
TRUMP_NOT = re.compile(r"\b(melania|ivanka|eric|tiffany|barron|lara|donald\s+trump\s+jr|don\s+jr|trump\s+jr)\b", re.I)
BIDEN = re.compile(r"\bbiden\b", re.I)
BIDEN_NOT = re.compile(r"\b(hunter|jill|ashley|beau)\s+biden", re.I)
HARRIS = re.compile(r"\b(kamala|harris)\b", re.I)
HARRIS_NOT = re.compile(r"\b(harris\s+county|harris\s+teeter|harris\s+poll|harris\s+interactive|"
                        r"(tobias|calvin|josh|kyle|dan|ed|emmylou|neil\s+patrick|naomie|maverick|"
                        r"devin|jalen|najee|joe|gary|lyndsey|jonathan|chris|kevin|damien|jarrod|"
                        r"zay|demetrius|anthony|will|richard|tommy|rachel|sean|ryan|bryce|teddy|"
                        r"brandon|mark|james|paul|ben|tim|greg|kamari|mike|michael|john|david|"
                        r"anita|taylor|keith|jaylen|mary|irie|rookie|ashlyn)\s+harris)\b", re.I)
AD = re.compile(r"(paid for by|advertisement|sponsored|sign up|subscribe|newsletter|^credit|"
                r"^photo|for the new york times$|getty images|associated press$)", re.I)
BOILER_DAYS = 5   # link text seen on this many days for one site = menu/promo, not news


def dem_name(d):
    return "Harris" if d >= SWITCH else "Biden"


def mentions(text, who):
    if who == "Trump":
        return bool(TRUMP.search(TRUMP_NOT.sub(" ", text)))
    if who == "Biden":
        return bool(BIDEN.search(BIDEN_NOT.sub(" ", text)))
    return bool(HARRIS.search(HARRIS_NOT.sub(" ", text)))


def first_pos(text, who):
    rx = {"Trump": (TRUMP, TRUMP_NOT), "Biden": (BIDEN, BIDEN_NOT), "Harris": (HARRIS, HARRIS_NOT)}[who]
    m = rx[0].search(rx[1].sub(lambda x: " " * len(x.group(0)), text))
    return m.start() if m else None


def is_headline(text, to_url):
    """Article headline (not menu/topic link): 4+ words, article-looking URL."""
    words = text.split()
    if len(words) < 4 or len(words) > 60 or AD.search(text):
        return False
    path = urlparse(to_url).path.rstrip("/")
    last = path.rsplit("/", 1)[-1]
    if re.search(r"/(topic|topics|tag|tags|category|section|people|person|hub|author|by)/", path + "/"):
        return False
    return bool(re.search(r"\d{4}", path) or last.count("-") >= 3 or re.search(r"\d", last) and len(last) >= 8)


def norm(text):
    return " ".join(text.split())


def boilerplate(raw_by_day):
    """{site: set(texts)} of link texts that recur on BOILER_DAYS+ days."""
    count = defaultdict(lambda: defaultdict(int))
    for got in raw_by_day.values():
        for k, v in got.items():
            for t in {norm(t) for _, t, _ in v["links"]}:
                count[k][t] += 1
    return {k: {t for t, n in c.items() if n >= BOILER_DAYS} for k, c in count.items()}


def load_all():
    raw = {}
    for d in days():
        path = os.path.join(RAW, d.strftime("%Y%m%d") + ".json.gz")
        if os.path.exists(path):
            with gzip.open(path, "rt") as fh:
                raw[d] = json.load(fh)
    return raw


def score(date, links, boiler=frozenset()):
    dem = dem_name(date)
    heads, seen = [], set()
    for order, text, to in links:
        text = norm(text)
        if text in boiler or not is_headline(text, to) or text in seen:
            continue
        seen.add(text)
        heads.append(text)
    rec = {"headlines": len(heads), "dem": dem}
    top, deep = heads[:TOP_N], heads
    rec["top_trump"] = int(any(mentions(t, "Trump") for t in top))
    rec["top_dem"] = int(any(mentions(t, dem) for t in top))
    rec["deep_trump"] = int(any(mentions(t, "Trump") for t in deep))
    rec["deep_dem"] = int(any(mentions(t, dem) for t in deep))
    first = ""
    for t in heads:
        a, b = first_pos(t, "Trump"), first_pos(t, dem)
        if a is None and b is None:
            continue
        first = "trump" if b is None or (a is not None and a < b) else "dem"
        break
    rec["first"] = first
    return rec, heads


MIN_HEADLINES = 15


def cmd_report(args):
    rows = []
    raw = load_all()
    boiler = boilerplate(raw)
    for d, got in raw.items():
        for k, v in got.items():
            rec, heads = score(d, v["links"], boiler.get(k, ()))
            if rec["headlines"] < MIN_HEADLINES:
                continue
            rows.append({"date": d.isoformat(), "paper": k, "name": SITES[k], "dem": rec["dem"],
                         "headlines": rec["headlines"], "top_trump": rec["top_trump"],
                         "top_dem": rec["top_dem"], "deep_trump": rec["deep_trump"],
                         "deep_dem": rec["deep_dem"], "first": rec["first"]})
    os.makedirs(os.path.join(ROOT, "dashboard"), exist_ok=True)
    out = os.path.join(ROOT, "dashboard", "paper_days.csv")
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    # quick summary
    by_day = defaultdict(list)
    for r in rows:
        by_day[(r["date"], r["dem"])].append(r)
    for era in ("Biden", "Harris"):
        ds = [v for (d, e), v in by_day.items() if e == era]
        if not ds:
            continue
        tp = sum(sum(r["top_trump"] for r in v) / len(v) for v in ds) / len(ds)
        dp = sum(sum(r["top_dem"] for r in v) / len(v) for v in ds) / len(ds)
        fr = [r["first"] for v in ds for r in v if r["first"]]
        print(f"{era}: days={len(ds)} trump_top={tp:.1%} {era.lower()}_top={dp:.1%} "
              f"trump_first={fr.count('trump')/max(1,len(fr)):.1%} of {len(fr)}")
    print(f"{len(rows)} usable homepage-days -> {out}")


def cmd_show(args):
    d = dt.date.fromisoformat(args.date)
    raw = load_all()
    boiler = boilerplate(raw)
    got = raw[d]
    for k in ([args.site] if args.site else sorted(got)):
        if k not in got:
            print(k, "MISSING"); continue
        rec, heads = score(d, got[k]["links"], boiler.get(k, ()))
        print(f"== {k} {rec}")
        for i, t in enumerate(heads[: args.n]):
            print(f"  {i:3d} {t[:110]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    sub.add_parser("report")
    s = sub.add_parser("show"); s.add_argument("date"); s.add_argument("--site"); s.add_argument("-n", type=int, default=15)
    a = ap.parse_args()
    {"fetch": cmd_fetch, "report": cmd_report, "show": cmd_show}[a.cmd](a)

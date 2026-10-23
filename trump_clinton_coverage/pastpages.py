#!/usr/bin/env python3
"""
Trump vs. Clinton front-page coverage from PastPages screenshots (May 8 - Nov 7 2016).

PastPages (pastpages.org, Ben Welsh) captured full-length screenshots of news
homepages every hour from 2012-2018 and stored them on archive.org
(collection "pastpages"). For each paper and day this script

  1. picks the capture nearest SNAPSHOT_HOUR_UTC (falling back to other captures
     the same day if one is blank / failed),
  2. OCRs the top OCR_DEPTH pixels and stores every text line with its y-position,
  3. records whether Trump / Clinton are mentioned
       * "top"  - in the first TOP_PX pixels (roughly the first screen), and
       * "deep" - anywhere in the first OCR_DEPTH pixels.

OCR output is cached, so thresholds and matching rules can be changed and the
results recomputed with `rescore` without touching the network or re-OCRing.

Usage:
  python3 pastpages.py index            # list captures for the window (cached)
  python3 pastpages.py run [--papers wsj,usatoday --start ... --end ... --workers 2]
  python3 pastpages.py rescore          # recompute matches + report from cached OCR
  python3 pastpages.py report
  python3 pastpages.py status
"""
import argparse
import datetime as dt
import io
import json
import logging
import re
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
from PIL import Image

import coverage as wb   # shared polite / outage-tolerant HTTP client

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data_pastpages"
OCR_DIR = DATA / "ocr"
ERRORS = DATA / "errors.jsonl"
LOG = DATA / "run.log"
INDEX = DATA / "index.json"
INTERIM = DATA / "interim"

DEFAULT_START = dt.date(2016, 5, 8)
DEFAULT_END = dt.date(2016, 11, 7)
SNAPSHOT_HOUR_UTC = 14     # ~10am Eastern
TOP_PX = 1200              # "top stories": roughly the first screen at 1024px width
OCR_DEPTH = 4000
MIN_LINES = 25             # fewer OCR lines than this => blank / broken capture
MIN_TOP_LINES = 20         # ...or fewer than this in the top region (e.g. page rendered without CSS)
MAX_TRIES_PER_DAY = 4

# US newspapers PastPages tracked through the whole 2016 window.
PAPERS = {
    "wall-street-journal":     "The Wall Street Journal",
    "usa-today":               "USA Today",
    "boston-globe":            "The Boston Globe",
    "philly-com":              "The Philadelphia Inquirer (philly.com)",
    "dallasnewscom":           "The Dallas Morning News",
    "denver-post":             "The Denver Post",
    "seattle-times":           "The Seattle Times",
    "stltoday":                "St. Louis Post-Dispatch",
    "san-francisco-chronicle": "San Francisco Chronicle",
    "spokesman-review":        "The Spokesman-Review (Spokane)",
    "cedar-rapids-gazette":    "The Gazette (Cedar Rapids)",
    "missourian":              "Columbia Missourian",
}

# Secondary group: US broadcast / online outlets, reported separately.
OUTLETS = {
    "cnn":           "CNN",
    "fox-news":      "Fox News",
    "npr":           "NPR",
    "drudge-report": "Drudge Report",
    "bloomberg":     "Bloomberg",
    "tpm":           "Talking Points Memo",
}

# Non-US newspapers with large American readerships (partial PastPages coverage).
INTL = {
    "daily-mail": "Daily Mail",
    "guardian":   "The Guardian",
}

# group -> (sites, daily csv, summary md, heading)
GROUPS = {
    "newspapers": (PAPERS, "pastpages_daily.csv", "pastpages_summary.md", "US newspaper front pages"),
    "outlets": (OUTLETS, "pastpages_outlets_daily.csv", "pastpages_outlets_summary.md",
                "US broadcast / online news homepages"),
    "intl": (INTL, "pastpages_intl_daily.csv", "pastpages_intl_summary.md",
             "UK newspapers widely read in the US"),
}
NAMES = {**PAPERS, **OUTLETS, **INTL}

# --- mention detection (tolerant of OCR dropping spaces) -----------------------
TRUMP_FAMILY = re.compile(r"(Melania|[Il]?vanka|Eric|Tiffany|Barron|Lara)\s*Trump|Trump,?\s*Jr|Donald\s*Trump\s*Jr", re.I)
TRUMP = re.compile(r"Trump(?![a-z])|TRUMP")
# Family members, plus Clinton the place (Clinton, Iowa / Missouri; the Clinton LumberKings play the Cedar Rapids Kernels)
CLINTON_FAMILY = re.compile(r"(Bill|Chelsea)\s*Clinton|Clinton\s*(County|Lumber\s*Kings|High|Township|Community|Lake|Iowa|Mo\b)"
                            r"|Clinton,\s*(Iowa|Mo)|Kernels.*Clinton|Clinton.*Kernels", re.I)
AD_LINE = re.compile(r"paid\s*for\s*by|advertisement|sponsored", re.I)   # campaign ads aren't coverage
CLINTON = re.compile(r"Hillary|HILLARY|Clinton(?![a-z])|CLINTON|\bHRC\b")


def mentions_trump(text):
    return bool(TRUMP.search(TRUMP_FAMILY.sub(" ", text)))


def mentions_clinton(text):
    return bool(CLINTON.search(CLINTON_FAMILY.sub(" ", text)))


# Papers near a town called Clinton (local sports): a bare "Clinton" needs campaign context on the same line.
CLINTON_TOWN_PAPERS = {"cedar-rapids-gazette"}
CAMPAIGN_CONTEXT = re.compile(r"Hillary|Trump|campaign|Dem|GOP|president|email|poll|vot|elect|nominee|Kaine|Pence", re.I)


def _local_fix(paper, text):
    if paper in CLINTON_TOWN_PAPERS and not CAMPAIGN_CONTEXT.search(text):
        return re.sub(r"Clinton", "", text)
    return text


def _pos(text, family, pat):
    blanked = family.sub(lambda m: " " * len(m.group(0)), text)   # keep offsets
    m = pat.search(blanked)
    return m.start() if m else None


def first_mention(lines):
    """('trump'|'clinton', y) for the candidate named first reading down the page, or ('', None).

    Lines are in page order (top to bottom, then left to right); when one line names
    both, the one earlier in the line wins.
    """
    for l in lines:
        t, c = _pos(l["t"], TRUMP_FAMILY, TRUMP), _pos(l["t"], CLINTON_FAMILY, CLINTON)
        if t is None and c is None:
            continue
        if c is None or (t is not None and t < c):
            return "trump", l["y"]
        return "clinton", l["y"]
    return "", None


# --- OCR ---------------------------------------------------------------------------
_ocr_local = threading.local()


def _engine():
    if not hasattr(_ocr_local, "eng"):
        from rapidocr_onnxruntime import RapidOCR
        _ocr_local.eng = RapidOCR()
    return _ocr_local.eng


def ocr_lines(img_bytes):
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    w, h = im.size
    lines = []
    # OCR in overlapping 1000px strips; keep a line only from the strip where it starts in the non-overlap part
    step, overlap = 1000, 80
    for top in range(0, min(h, OCR_DEPTH), step):
        strip = im.crop((0, top, w, min(top + step + overlap, h)))
        res, _ = _engine()(np.array(strip))
        for box, text, conf in res or []:
            y = int(box[0][1]) + top
            if y >= top + step and top + step < min(h, OCR_DEPTH):
                continue    # belongs to the next strip
            lines.append({"y": y, "x": int(box[0][0]), "h": int(box[3][1] - box[0][1]),
                          "c": round(float(conf), 3), "t": text})
    lines.sort(key=lambda l: (l["y"], l["x"]))
    return {"width": w, "height": h, "lines": lines}


# --- index of captures ---------------------------------------------------------------
def build_index(args):
    if INDEX.exists() and not args.refresh:
        idx = json.loads(INDEX.read_text())
        if all(s in idx for s in NAMES):
            return idx
    slugs = " OR ".join(NAMES)
    q = (f"collection:pastpages AND pastpages_site_slug:({slugs}) AND "
         f"date:[{DEFAULT_START}T00:00:00Z TO {DEFAULT_END + dt.timedelta(days=1)}T12:00:00Z]")
    params = {"q": q, "fields": "identifier,pastpages_site_slug,date", "count": 10000}
    items = []
    while True:
        r = wb.http_get("https://archive.org/services/search/v1/scrape?" +
                        "&".join(f"{k}={wb.requests.utils.quote(str(v))}" for k, v in params.items()))
        d = r.json()
        items += d.get("items", [])
        if "cursor" not in d:
            break
        params["cursor"] = d["cursor"]
    idx = defaultdict(list)
    for it in items:
        idx[it["pastpages_site_slug"]].append([it["date"], it["identifier"]])
    for v in idx.values():
        v.sort()
    INDEX.write_text(json.dumps(idx))
    logging.info("index: %d captures for %d papers", len(items), len(idx))
    return idx


def candidates_for_day(caps, day):
    target = dt.datetime(day.year, day.month, day.day, SNAPSHOT_HOUR_UTC, tzinfo=dt.timezone.utc)
    lo, hi = target - dt.timedelta(hours=12), target + dt.timedelta(hours=12)
    out = []
    for ts, ident in caps:
        t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if lo <= t <= hi:
            out.append((abs((t - target).total_seconds()), ts, ident))
    out.sort()
    return out[:MAX_TRIES_PER_DAY]


# --- per-item pipeline -----------------------------------------------------------------
def ocr_path(slug, day):
    return OCR_DIR / slug / f"{day.isoformat()}.json"


def log_error(slug, day, msg):
    with wb._rate_lock:
        with open(ERRORS, "a") as f:
            f.write(json.dumps({"paper": slug, "date": day.isoformat(), "error": msg,
                                "at": dt.datetime.utcnow().isoformat(timespec="seconds")}) + "\n")


def fetch_screenshot(ident):
    meta = wb.http_get(f"https://archive.org/metadata/{ident}").json()
    names = [f["name"] for f in meta.get("files", []) if f["name"].endswith("-image.jpg")]
    if not names:
        raise wb.FetchError(f"no -image.jpg in {ident}")
    return wb.http_get(f"https://archive.org/download/{ident}/{names[0]}", timeout=180).content


def good_capture(lines):
    return len(lines) >= MIN_LINES and sum(l["y"] < TOP_PX for l in lines) >= MIN_TOP_LINES


def score(rec):
    all_lines = rec.get("lines", [])
    lines = [{**l, "t": _local_fix(rec.get("paper"), l["t"])} for l in all_lines if not AD_LINE.search(l["t"])]
    top = " \n".join(l["t"] for l in lines if l["y"] < TOP_PX)
    deep = " \n".join(l["t"] for l in lines)
    rec.update({
        "usable": good_capture(all_lines),
        "top_trump": mentions_trump(top), "top_clinton": mentions_clinton(top),
        "deep_trump": mentions_trump(deep), "deep_clinton": mentions_clinton(deep),
        "top_trump_lines": sum(mentions_trump(l["t"]) for l in lines if l["y"] < TOP_PX),
        "top_clinton_lines": sum(mentions_clinton(l["t"]) for l in lines if l["y"] < TOP_PX),
    })
    rec["first"], rec["first_y"] = first_mention(lines)
    return rec


def process(slug, day, caps):
    out = ocr_path(slug, day)
    if out.exists():
        return "skip"
    cands = candidates_for_day(caps, day)
    rec = {"paper": slug, "date": day.isoformat(), "capture": None, "lines": [], "tried": []}
    try:
        for _, ts, ident in cands:
            img = fetch_screenshot(ident)
            o = ocr_lines(img)
            rec.update(capture=ident, captured_at=ts, width=o["width"], height=o["height"], lines=o["lines"])
            rec["tried"].append([ident, len(o["lines"])])
            if good_capture(o["lines"]):
                break
        score(rec)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rec, ensure_ascii=False))
        if not cands:
            return "nocapture"
        return "ok" if rec["usable"] else "unusable"
    except Exception as e:  # noqa: BLE001 - logged; retried on the next run
        log_error(slug, day, f"{type(e).__name__}: {e}")
        return "error"


def daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += dt.timedelta(days=1)


# --- commands ---------------------------------------------------------------------------
def cmd_index(args):
    idx = build_index(args)
    for slug in NAMES:
        days = {c[0][:10] for c in idx.get(slug, [])}
        logging.info("%-25s %5d captures on %3d days", slug, len(idx.get(slug, [])), len(days))


def cmd_run(args):
    idx = build_index(args)
    papers = args.papers.split(",") if args.papers else list(GROUPS[args.group][0])
    days = list(daterange(args.start, args.end))
    # Coarse-to-fine day order (every 8th day, then the midpoints, ...) so interim
    # results already span the whole window.
    order = {r: i for i, r in enumerate([0, 4, 2, 6, 1, 5, 3, 7])}
    days.sort(key=lambda d: (order[(d - args.start).days % 8], d))
    todo = [(s, d) for d in days for s in papers if not ocr_path(s, d).exists()]
    logging.info("run: %d papers x %d days, %d to do", len(papers), len(days), len(todo))
    counts = defaultdict(int)
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        futs = {ex.submit(process, s, d, idx.get(s, [])): (s, d) for s, d in todo}
        for i, f in enumerate(as_completed(futs), 1):
            s, d = futs[f]
            res = f.result()
            counts[res] += 1
            if res != "ok":
                logging.info("%s %s -> %s", s, d, res)
            if i % 10 == 0 or i == len(todo):
                rate = i / (time.time() - t0)
                logging.info("PROGRESS %d/%d %s  %.1f items/min  ETA %.1f h",
                             i, len(todo), dict(counts), rate * 60, (len(todo) - i) / rate / 3600)
            if i % 50 == 0:
                cmd_report(args, out_dir=INTERIM)
    cmd_report(args)
    logging.info("DONE %s", dict(counts))


def load_recs():
    return [json.loads(p.read_text()) for p in sorted(OCR_DIR.glob("*/*.json"))]


def cmd_rescore(args):
    n = 0
    for p in OCR_DIR.glob("*/*.json"):
        rec = score(json.loads(p.read_text()))
        p.write_text(json.dumps(rec, ensure_ascii=False))
        n += 1
    logging.info("rescored %d", n)
    cmd_report(args)


def cmd_report(args, out_dir=ROOT):
    """Interim reports during a run go to data_pastpages/interim (untracked); final ones to ROOT."""
    out_dir.mkdir(parents=True, exist_ok=True)
    recs = [r for r in load_recs() if r.get("usable")]
    for group, (sites, csv_name, md_name, heading) in GROUPS.items():
        report_group([r for r in recs if r["paper"] in sites], sites, out_dir / csv_name, out_dir / md_name, heading)


def report_group(recs, sites, csv_path, md_path, heading):
    by_day = defaultdict(list)
    for r in recs:
        by_day[r["date"]].append(r)

    def pct(rows, f):
        return round(100 * sum(r[f] for r in rows) / len(rows), 1) if rows else 0.0

    lines = ["date,papers_checked,pct_top_trump,pct_top_clinton,pct_deep_trump,pct_deep_clinton,"
             "top_trump_lines,top_clinton_lines,first_trump,first_clinton"]
    for day in sorted(by_day):
        rows = by_day[day]
        lines.append(",".join(str(x) for x in [
            day, len(rows), pct(rows, "top_trump"), pct(rows, "top_clinton"),
            pct(rows, "deep_trump"), pct(rows, "deep_clinton"),
            sum(r["top_trump_lines"] for r in rows), sum(r["top_clinton_lines"] for r in rows),
            sum(r.get("first") == "trump" for r in rows), sum(r.get("first") == "clinton" for r in rows)]))
    csv_path.write_text("\n".join(lines) + "\n")

    summ = [f"# Trump vs. Clinton on {heading} (PastPages screenshots)", "",
            f"Window {DEFAULT_START} - {DEFAULT_END}. One capture per paper per day, nearest "
            f"{SNAPSHOT_HOUR_UTC}:00 UTC (~10am ET). \"Top\" = text OCR'd in the first {TOP_PX}px of the "
            f"homepage (≈ first screen); \"deep\" = first {OCR_DEPTH}px.", ""]
    if recs:
        dp = [(pct(v, "top_trump"), pct(v, "top_clinton"), pct(v, "deep_trump"), pct(v, "deep_clinton"))
              for v in by_day.values()]
        mean = lambda i: sum(x[i] for x in dp) / len(dp)  # noqa: E731
        tw = sum(a > b for a, b, *_ in dp)
        cw = sum(b > a for a, b, *_ in dp)
        summ += [f"- Usable paper-days: {len(recs)} over {len(by_day)} days",
                 f"- Mean daily % of papers with **Trump** in top stories: **{mean(0):.1f}%**",
                 f"- Mean daily % of papers with **Clinton** in top stories: **{mean(1):.1f}%**",
                 f"- Days Trump % > Clinton %: {tw}; Clinton > Trump: {cw}; tied: {len(dp) - tw - cw}",
                 f"- Deeper ({OCR_DEPTH}px) - Trump {mean(2):.1f}% vs Clinton {mean(3):.1f}%"]
        named = [r for r in recs if r.get("first")]
        ft = sum(r["first"] == "trump" for r in named)
        fdays = [(sum(r.get("first") == "trump" for r in v), sum(r.get("first") == "clinton" for r in v))
                 for v in by_day.values()]
        if named:
            summ += [f"- **Named first** (reading down the page, of {len(named)} front pages naming either): "
                     f"Trump **{100 * ft / len(named):.1f}%**, Clinton **{100 * (len(named) - ft) / len(named):.1f}%**; "
                     f"days more papers named Trump first: {sum(a > b for a, b in fdays)}, "
                     f"Clinton first: {sum(b > a for a, b in fdays)}, tied: {sum(a == b for a, b in fdays)}"]
        summ += ["", "| paper | days | % days Trump on top | % days Clinton on top | Trump named first | Clinton named first |",
                 "|---|---|---|---|---|---|"]
        by_paper = defaultdict(list)
        for r in recs:
            by_paper[r["paper"]].append(r)
        for s in sites:
            v = by_paper.get(s, [])
            if v:
                nf = sum(1 for r in v if r.get("first"))
                ftp = round(100 * sum(r.get("first") == "trump" for r in v) / nf, 1) if nf else ""
                fcp = round(100 - ftp, 1) if nf else ""
                summ.append(f"| {sites[s]} | {len(v)} | {pct(v, 'top_trump')} | {pct(v, 'top_clinton')} | {ftp}% | {fcp}% |")
        # monthly
        by_month = defaultdict(list)
        for d, v in by_day.items():
            by_month[d[:7]].append((pct(v, "top_trump"), pct(v, "top_clinton"),
                                    sum(r.get("first") == "trump" for r in v), sum(r.get("first") == "clinton" for r in v)))
        summ += ["", "| month | mean % Trump on top | mean % Clinton on top | Trump named first | Clinton named first |",
                 "|---|---|---|---|---|"]
        for m in sorted(by_month):
            v = by_month[m]
            ft_m, fc_m = sum(x[2] for x in v), sum(x[3] for x in v)
            share = f"{100 * ft_m / (ft_m + fc_m):.0f}% | {100 * fc_m / (ft_m + fc_m):.0f}%" if ft_m + fc_m else " | "
            summ.append(f"| {m} | {sum(x[0] for x in v) / len(v):.1f} | {sum(x[1] for x in v) / len(v):.1f} | {share} |")
    md_path.write_text("\n".join(summ) + "\n")
    logging.info("report %s: %d usable paper-days over %d days", md_path, len(recs), len(by_day))


def cmd_status(args):
    all_recs = load_recs()
    ndays = len(list(daterange(DEFAULT_START, DEFAULT_END)))
    for group, (sites, *_) in GROUPS.items():
        recs = [r for r in all_recs if r["paper"] in sites]
        usable = sum(1 for r in recs if r.get("usable"))
        print(f"{group:11s} done {len(recs)}/{len(sites) * ndays}  usable {usable}  "
              f"no-capture {sum(1 for r in recs if not r.get('capture'))}")
    errs = sum(1 for _ in open(ERRORS)) if ERRORS.exists() else 0
    print(f"error-log lines {errs}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["index", "run", "rescore", "report", "status"])
    ap.add_argument("--start", type=dt.date.fromisoformat, default=DEFAULT_START)
    ap.add_argument("--end", type=dt.date.fromisoformat, default=DEFAULT_END)
    ap.add_argument("--papers")
    ap.add_argument("--group", choices=list(GROUPS), default="newspapers")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--refresh", action="store_true", help="rebuild the capture index")
    args = ap.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.FileHandler(LOG), logging.StreamHandler(sys.stdout)])
    {"index": cmd_index, "run": cmd_run, "rescore": cmd_rescore,
     "report": cmd_report, "status": cmd_status}[args.cmd](args)


if __name__ == "__main__":
    main()

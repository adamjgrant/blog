#!/usr/bin/env python3
"""Write dashboard/paper_days.csv (one row per usable paper-day) for the results page."""
import csv
import json
from pathlib import Path

import pastpages as pp

OUT = Path(__file__).resolve().parent / "dashboard"


def main():
    OUT.mkdir(exist_ok=True)
    group_of = {s: g for g, (sites, *_) in pp.GROUPS.items() for s in sites}
    rows = []
    for r in pp.load_recs():
        if not r.get("usable") or r["paper"] not in group_of:
            continue
        rows.append({"date": r["date"], "paper": r["paper"], "name": pp.NAMES[r["paper"]],
                     "group": group_of[r["paper"]],
                     "top_trump": int(r["top_trump"]), "top_clinton": int(r["top_clinton"]),
                     "deep_trump": int(r["deep_trump"]), "deep_clinton": int(r["deep_clinton"]),
                     "first": r.get("first", "")})
    rows.sort(key=lambda x: (x["date"], x["paper"]))
    with open(OUT / "paper_days.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["date"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} paper-days -> {OUT / 'paper_days.csv'}")


if __name__ == "__main__":
    main()

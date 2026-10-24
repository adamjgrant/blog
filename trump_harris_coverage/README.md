# Trump vs. Biden/Harris on news homepages, 2024

For each day from May 5 to Nov 4, 2024, what share of 45 news homepages had
Donald Trump in their top stories, versus his Democratic opponent (Joe Biden
through July 21, Kamala Harris from July 22), and which candidate a reader
met first. Companion to `../trump_clinton_coverage` (2016).

Results page: https://claude.ai/artifact/Tg74K1c7xSeUyHJ5PJWt7v

## Method

- **Source**: GDELT Global Frontpage Graph (`data.gdeltproject.org/gdeltv3/gfg/alpha/`),
  which records every link on ~50,000 news homepages each hour with its text and
  order on the page. One capture per site per day at 14:00 UTC (10am ET), falling
  back to 15/13/16/12 UTC for sites missing from that hour.
- **Headlines**: links with 4+ words pointing at an article-like URL; menus,
  topic pages, promos and any link text recurring on 14+ days for a site are dropped.
  A homepage with fewer than 15 headlines is left out.
- **Top stories**: the first 10 headlines. **Named first**: the first headline
  naming either candidate; within a headline, the earlier name wins.
- Trump's family, Hunter/Jill Biden and other people named Harris are excluded.

## Results

| Period | Days | Trump in top stories | Opponent in top stories | Trump named first |
|---|---|---|---|---|
| vs. Biden (May 5 – Jul 21) | 78 | 44.6% | 37.4% | 56.3% of 3,036 |
| vs. Harris (Jul 22 – Nov 4) | 106 | 49.1% | 47.5% | 52.5% of 4,382 |
| All | 184 | 47.2% | 43.2% | 54.1% of 7,418 |

Not in the archive: Washington Post, WSJ, USA Today, AP, Reuters. CNN's homepage
is present on 70 days; the Pittsburgh Post-Gazette was dropped (headlines load by script).

## Run

    python3 gfg.py fetch    # ~30s/day, resumable; writes data/raw/YYYYMMDD.json.gz
    python3 gfg.py report   # writes dashboard/paper_days.csv and prints a summary
    python3 gfg.py show 2024-09-10 --site nytimes.com   # inspect one homepage

# Trump vs. Clinton on the front page, 2016

How often did major US news homepages put each 2016 presidential candidate in
their top stories, and which one did a reader meet first? One capture per
publication per day, nearest 10am Eastern, May 8 – Nov 7, 2016.

Results page: https://claude.ai/artifact/1pZEfhfVq4oSvdHhDETBnd

## Results

| | US newspapers (12) | US TV & online (5) | UK papers read in the US (2) |
|---|---|---|---|
| Front pages read | 1,980 | 829 | 197 |
| Avg. share with Trump in the first screen | 36% | 71% | 32% |
| Avg. share with Clinton in the first screen | 27% | 63% | 25% |
| Trump named first (of pages naming either) | 65% | 55% | 63% |

Full tables: `pastpages_summary.md`, `pastpages_outlets_summary.md`,
`pastpages_intl_summary.md`; per-day CSVs alongside; one row per front page in
`dashboard/paper_days.csv`.

## Method

- **Source:** PastPages (pastpages.org) homepage screenshots, archived on
  archive.org, read with OCR (RapidOCR). The Wayback Machine route in
  `coverage.py` was blocked from the environment this ran in.
- **Top stories:** any text in the first 1,200 px of the page (about one
  screen). "Deep" counts the first 4,000 px.
- **Named first:** reading down the page, the candidate mentioned first; when
  one line names both, the one earlier in the line.
- **Not counted:** Melania, Ivanka, Eric, Tiffany, Barron, Lara, Don Jr., Bill
  and Chelsea; paid ads; Clinton, Iowa (local sports in the Cedar Rapids
  Gazette).
- **Gaps:** NYT and Washington Post aren't in PastPages for 2016. NPR was
  dropped (captures render without CSS). The Denver Post and philly.com lose
  many days to broken captures; The Guardian was captured on only 48 days.

## Running it

```
pip install requests beautifulsoup4 lxml rapidocr_onnxruntime
./run_all.sh                    # newspapers, outlets, intl; resumable
python3 pastpages.py rescore    # re-apply matching rules to cached OCR
python3 export_dashboard.py     # dashboard/paper_days.csv
```

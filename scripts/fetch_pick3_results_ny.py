"""
Pulls NY Pick 3 (branded "Numbers" by NY Lottery) drawing history by
scraping nylottery.org's results page, instead of New York State's
official Open Data portal (data.ny.gov).

WHY NOT data.ny.gov: that Socrata dataset (hsys-3def) is official but
lags real draws by a couple of days - it's an archival export, not a
live feed. Polling it more often doesn't help since the staleness is
in the source, not the fetch schedule. See git history for the old
version of this script if that dataset is ever needed again.

Page: https://www.nylottery.org/numbers/results

IMPORTANT CAVEAT - MARKUP NOT VISUALLY VERIFIED:
Unlike fetch_pick3_results_sc.py (whose CSS selectors were confirmed
against real rendered HTML), this script was written against a
text-extracted copy of the page, not the raw HTML source - so exact
tag/class names weren't available to select against. To make the
parser resilient to that, it flattens the page to plain text and
regex-matches this repeating pattern instead of relying on CSS
selectors:
    <Weekday> <Month> <Day><suffix> <Year>
    Midday: D D D            (or "Still to be drawn...")
    Evening: D D D           (or "Still to be drawn...")
Example: "Friday July 26th 2024 Midday: 8 8 7 Evening: 9 4 8"

BEFORE RELYING ON THIS ON A SCHEDULE: run it once via
workflow_dispatch (or locally) and confirm the printed "Latest:" line
looks right. If it errors or comes up empty, the site's actual markup
may not match the assumed text pattern above - fetch the live page
and adjust DRAW_PATTERN.

NOTE ON SOURCE: nylottery.org is a third-party lottery-results site
(not an .ny.gov government domain). It appears to publish same-day
results, but isn't the state's own data. Worth spot-checking against
nylottery.ny.gov occasionally, and worth re-checking their terms of
use periodically since it's not our own official partner source.

Like SC, this page only shows a rolling recent window (about the last
week), not deep history - so results are MERGED into whatever already
exists in the output file rather than overwriting it, same as
fetch_pick3_results_sc.py. History will grow gradually rather than
starting complete; consider re-seeding once with the old data.ny.gov
dataset's history if a cleaner backfill is wanted later.

Writes/updates data/pick3/ny-history.json in the shape pick3-stats.js
expects:
  { updated_at, state: "ny", draws: [
      { draw_date, draw_time: "midday"|"evening", digits: [h,t,o], fireball: null }
  ]}
NY's Numbers game has no Fireball-style bonus digit, so fireball is
always null here - matches the front-end's hasFireball: false for ny.

Run on a schedule via .github/workflows/update-pick3-ny.yml (same
workflow file as before, just needs beautifulsoup4 added to its
install step now that this script uses BeautifulSoup).
"""

import os
import re
import json
import datetime
import requests
from bs4 import BeautifulSoup

PAGE_URL = "https://www.nylottery.org/numbers/results"
OUTPUT_PATH = "data/pick3/ny-history.json"

MONTHS = (
    "January|February|March|April|May|June|July|August|"
    "September|October|November|December"
)

# Matches one full draw-day block, tolerant of whatever whitespace is
# left after flattening the page to plain text. Each of the midday /
# evening groups is EITHER three space-separated digits OR the
# "Still to be drawn..." placeholder text (captured but ignored).
DRAW_PATTERN = re.compile(
    r"(?P<weekday>Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday)\s+"
    r"(?P<month>" + MONTHS + r")\s+"
    r"(?P<day>\d{1,2})(?:st|nd|rd|th)\s+"
    r"(?P<year>\d{4})\s+"
    r"Midday:\s*(?P<midday>\d\s*\d\s*\d|Still to be drawn\.{3})\s+"
    r"Evening:\s*(?P<evening>\d\s*\d\s*\d|Still to be drawn\.{3})",
    re.IGNORECASE,
)


def fetch_page_text():
    resp = requests.get(PAGE_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    # Flatten to plain text with single spaces between tags' text nodes -
    # matches the shape DRAW_PATTERN expects regardless of the actual
    # element structure (table, divs, etc.) wrapping each field.
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))


def parse_digits(raw):
    if not raw or "still to be drawn" in raw.lower():
        return None
    digits = re.findall(r"\d", raw)
    if len(digits) != 3:
        return None
    return [int(d) for d in digits]


def parse_draws(text):
    draws = []
    for m in DRAW_PATTERN.finditer(text):
        try:
            draw_date = datetime.date(
                int(m.group("year")),
                datetime.datetime.strptime(m.group("month"), "%B").month,
                int(m.group("day")),
            ).isoformat()
        except ValueError:
            continue  # malformed date - skip rather than guess

        midday_digits = parse_digits(m.group("midday"))
        if midday_digits:
            draws.append({"draw_date": draw_date, "draw_time": "midday", "digits": midday_digits, "fireball": None})

        evening_digits = parse_digits(m.group("evening"))
        if evening_digits:
            draws.append({"draw_date": draw_date, "draw_time": "evening", "digits": evening_digits, "fireball": None})

    return draws


def load_existing():
    if not os.path.exists(OUTPUT_PATH):
        return []
    with open(OUTPUT_PATH) as f:
        return json.load(f).get("draws", [])


def merge_draws(existing, scraped):
    seen = {(d["draw_date"], d["draw_time"]) for d in existing}
    merged = list(existing)
    added = 0
    for d in scraped:
        key = (d["draw_date"], d["draw_time"])
        if key not in seen:
            merged.append(d)
            seen.add(key)
            added += 1
    merged.sort(key=lambda d: (d["draw_date"], d["draw_time"]))
    return merged, added


def main():
    text = fetch_page_text()
    scraped = parse_draws(text)

    if not scraped:
        raise RuntimeError(
            "No draws parsed from nylottery.org - the page's markup/text "
            "pattern may not match DRAW_PATTERN. Fetch the live page and "
            "check it still reads like 'Friday July 26th 2024 Midday: "
            "8 8 7 Evening: 9 4 8' once flattened to text."
        )

    existing = load_existing()
    merged, added = merge_draws(existing, scraped)

    output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "state": "ny",
        "note": (
            "Built incrementally by scraping nylottery.org's results page "
            "each run (a third-party site, not data.ny.gov's official but "
            "laggy open-data export) - no deep bulk history from this "
            "source, so history grows over time rather than starting "
            "complete. NY's Numbers game has no Fireball-equivalent bonus digit."
        ),
        "draws": merged,
    }

    os.makedirs("data/pick3", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Scraped {len(scraped)} draws from the page, added {added} new ones.")
    print(f"Total draws in history: {len(merged)}")
    if merged:
        latest = merged[-1]
        print(f"Latest: {latest['draw_date']} {latest['draw_time']} - {latest['digits']}")


if __name__ == "__main__":
    main()

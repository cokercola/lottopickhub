"""
Pulls SC Pick 3 Plus FIREBALL results by scraping the "Winning Numbers
for the Most Recent Drawings" section of the official Pick 3 page.

Page: https://www.sceducationlottery.com/Games/Pick3

CONFIRMED MARKUP (verified against real page source, not guessed):
  <div class="col-md-2" style="min-width:250px; display:inline-block;">
    <p class="numbers-date">8/9/2026 - Evening</p>
    <span class="number-circle">6</span>
    <span class="number-circle">0</span>
    <span class="number-circle">8</span>
    <span class="number-circle-fireball-pick3">4</span>
  </div>
One such div per drawing. The page only shows the last several draws
at a time (roughly the last 6), not a deep archive.

IMPORTANT DIFFERENCE FROM THE VA/NC SCRIPTS: those two return the
ENTIRE history in one request, so their scripts overwrite the output
file from scratch every run. SC has no such bulk export - there's a
POST search form (action="/Search/SearchP3") on the page that likely
returns deeper history, but its required form fields haven't been
confirmed, so this script does NOT use it yet.

Because of that, this script MERGES newly scraped draws into whatever
history already exists in the output file, rather than overwriting
it. Run twice daily (matching SC's actual midday/evening schedule),
this builds up a real history gradually - it will just start smaller
than VA/NC's day-one backfill and take a few weeks to become useful
for hot/cold and heatmap stats.

Writes/updates data/pick3/sc-history.json in the shape pick3-stats.js
expects:
  { updated_at, state: "sc", draws: [
      { draw_date, draw_time: "midday"|"evening", digits: [h,t,o], fireball: N }
  ]}

Run on a schedule via .github/workflows/update-pick3-sc.yml (follow
the same pattern as update-pick3-va.yml / update-pick3-nc.yml).
"""

import os
import re
import json
import datetime
import requests
from bs4 import BeautifulSoup

PAGE_URL = "https://www.sceducationlottery.com/Games/Pick3"
OUTPUT_PATH = "data/pick3/sc-history.json"

DATE_PATTERN = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})\s*-\s*(\w+)")
SESSION_MAP = {"evening": "evening", "midday": "midday", "day": "midday"}


def fetch_page_html():
    resp = requests.get(PAGE_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return resp.text


def parse_draws(html):
    soup = BeautifulSoup(html, "html.parser")
    draws = []

    for block in soup.select("div.col-md-2"):
        date_el = block.select_one("p.numbers-date")
        if not date_el:
            continue  # not a draw block - col-md-2 is used elsewhere on the page too

        m = DATE_PATTERN.search(date_el.get_text(strip=True))
        if not m:
            continue

        month, day, year, session_raw = m.group(1), m.group(2), m.group(3), m.group(4).lower()
        draw_time = SESSION_MAP.get(session_raw)
        if not draw_time:
            continue  # unrecognized session label - skip rather than guess

        digit_spans = block.select("span.number-circle")
        fireball_span = block.select_one("span.number-circle-fireball-pick3")
        if len(digit_spans) != 3 or not fireball_span:
            continue  # malformed block - skip rather than write bad data

        try:
            digits = [int(s.get_text(strip=True)) for s in digit_spans]
            fireball = int(fireball_span.get_text(strip=True))
        except ValueError:
            continue

        draw_date = f"{year}-{int(month):02d}-{int(day):02d}"
        draws.append({"draw_date": draw_date, "draw_time": draw_time, "digits": digits, "fireball": fireball})

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
    html = fetch_page_html()
    scraped = parse_draws(html)

    if not scraped:
        raise RuntimeError(
            "No draws parsed from the SC page - the markup may have "
            "changed. Check for div.col-md-2 > p.numbers-date on the live page."
        )

    existing = load_existing()
    merged, added = merge_draws(existing, scraped)

    output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "state": "sc",
        "note": (
            "Built incrementally by scraping the recent-draws section of "
            "the official SC Pick 3 page each run - no bulk history export "
            "exists for this state, so history grows over time rather than "
            "starting complete."
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
        print(f"Latest: {latest['draw_date']} {latest['draw_time']} - {latest['digits']} (FB {latest['fireball']})")


if __name__ == "__main__":
    main()

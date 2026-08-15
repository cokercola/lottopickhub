"""
Pulls SC Pick 4 Plus FIREBALL results by scraping the "Winning Numbers
for the Most Recent Drawings" section of the official Pick 4 page.

Page: https://www.sceducationlottery.com/Games/Pick4 (assumed URL,
following the same /Games/PickN pattern as the confirmed Pick 3 page -
NOT yet verified this session. Check it resolves before relying on
this script.)

ASSUMED MARKUP (same structure as the confirmed Pick 3 page, with a
4th number-circle and a Pick-4-specific fireball class name guessed
by analogy - NOT verified against real Pick 4 page source):
  <div class="col-md-2" style="min-width:250px; display:inline-block;">
    <p class="numbers-date">8/9/2026 - Evening</p>
    <span class="number-circle">6</span>
    <span class="number-circle">0</span>
    <span class="number-circle">8</span>
    <span class="number-circle">4</span>
    <span class="number-circle-fireball-pick4">2</span>
  </div>
Before running on a schedule: view-source the live Pick 4 page and
confirm both the page URL and the fireball span's class name
(number-circle-fireball-pick4 is a guess by analogy with Pick 3's
number-circle-fireball-pick3 - it may use a different suffix or none
at all). If the fireball selector comes back empty, the script still
parses the 4 base digits fine (fireball just stays null) - see
parse_draws() below.

Same incremental-merge approach as the Pick 3 SC script: no bulk
history export is known for this state, so history builds up over
time from whatever the page shows on each run (roughly the last 6
draws), rather than starting complete.

Writes/updates data/pick4/sc-history.json in the shape pick4-stats.js
expects:
  { updated_at, state: "sc", draws: [
      { draw_date, draw_time: "midday"|"evening", digits: [th,h,t,o], fireball: N|null }
  ]}

Run on a schedule via .github/workflows/update-pick4-sc.yml, same
pattern as update-pick3-sc.yml.
"""

import os
import re
import json
import datetime
import requests
from bs4 import BeautifulSoup

PAGE_URL = "https://www.sceducationlottery.com/Games/Pick4"
OUTPUT_PATH = "data/pick4/sc-history.json"

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
            continue

        m = DATE_PATTERN.search(date_el.get_text(strip=True))
        if not m:
            continue

        month, day, year, session_raw = m.group(1), m.group(2), m.group(3), m.group(4).lower()
        draw_time = SESSION_MAP.get(session_raw)
        if not draw_time:
            continue

        digit_spans = block.select("span.number-circle")
        fireball_span = block.select_one("span.number-circle-fireball-pick4")
        if len(digit_spans) != 4:
            continue  # malformed block - skip rather than write bad data

        try:
            digits = [int(s.get_text(strip=True)) for s in digit_spans]
            fireball = int(fireball_span.get_text(strip=True)) if fireball_span else None
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
            "No draws parsed from the SC Pick 4 page - either the page URL "
            "is wrong or the markup differs from the Pick 3 page's pattern. "
            "View-source the live page and check div.col-md-2 > p.numbers-date."
        )

    existing = load_existing()
    merged, added = merge_draws(existing, scraped)

    output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "state": "sc",
        "note": (
            "Built incrementally by scraping the recent-draws section of "
            "the official SC Pick 4 page each run - no bulk history export "
            "exists for this state, so history grows over time rather than "
            "starting complete."
        ),
        "draws": merged,
    }

    os.makedirs("data/pick4", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Scraped {len(scraped)} draws from the page, added {added} new ones.")
    print(f"Total draws in history: {len(merged)}")
    if merged:
        latest = merged[-1]
        print(f"Latest: {latest['draw_date']} {latest['draw_time']} - {latest['digits']} (FB {latest['fireball']})")


if __name__ == "__main__":
    main()

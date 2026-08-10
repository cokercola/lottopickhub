"""
Pulls Virginia Pick 3 drawing history from the Virginia Lottery's own
public API - a plain-text export, not a scraper against a rendered
page. Confirmed working and returns years of history in a single
request (no pagination needed).

Endpoint: https://www.valottery.com/api/v1/downloadall?gameId=1050
Response is plain text, one line per date, in this exact format:
  M/D/YYYY; Day: d1,d2,d3; Fireball: f; Night: d1,d2,d3; Fireball: f
Example line:
  8/8/2026; Day: 9,5,3; Fireball: 5; Night: 2,8,0; Fireball: 2

Unlike the NY Pick 3 script, this format was verified directly against
a live response in this session - no field-name guessing here.

Writes data/pick3/va-history.json in the shape pick3-stats.js expects:
  { updated_at, state: "va", draws: [
      { draw_date, draw_time: "midday"|"evening", digits: [h,t,o], fireball: N }
  ]}
VA's "Day" drawing maps to draw_time "midday" and "Night" maps to
"evening" to match the field names the other states' scripts and the
front-end already use.

Run on a schedule via .github/workflows/update-pick3-va.yml (create
following the same pattern as update-powerball.yml, but note VA draws
twice daily so this needs to run more often than the weekly/multi-
weekly jackpot game workflows).
"""

import os
import re
import json
import datetime
import requests

API_URL = "https://www.valottery.com/api/v1/downloadall?gameId=1050"
OUTPUT_PATH = "data/pick3/va-history.json"

# Matches: 8/8/2026; Day: 9,5,3; Fireball: 5; Night: 2,8,0; Fireball: 2
LINE_PATTERN = re.compile(
    r"(\d{1,2})/(\d{1,2})/(\d{4});\s*"
    r"Day:\s*(\d),(\d),(\d);\s*Fireball:\s*(\d);\s*"
    r"Night:\s*(\d),(\d),(\d);\s*Fireball:\s*(\d)"
)


def fetch_raw_text():
    resp = requests.get(API_URL, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_lines(raw_text):
    draws = []
    for line in raw_text.splitlines():
        m = LINE_PATTERN.search(line)
        if not m:
            continue  # skips the "Results for Pick 3" header line and any blanks

        month, day, year = m.group(1), m.group(2), m.group(3)
        draw_date = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

        day_digits = [int(m.group(4)), int(m.group(5)), int(m.group(6))]
        day_fireball = int(m.group(7))
        night_digits = [int(m.group(8)), int(m.group(9)), int(m.group(10))]
        night_fireball = int(m.group(11))

        draws.append({"draw_date": draw_date, "draw_time": "midday", "digits": day_digits, "fireball": day_fireball})
        draws.append({"draw_date": draw_date, "draw_time": "evening", "digits": night_digits, "fireball": night_fireball})

    return draws


def main():
    raw_text = fetch_raw_text()
    draws = parse_lines(raw_text)

    if not draws:
        raise RuntimeError(
            "No draws parsed from the VA API response - the text format "
            "may have changed. Print raw_text[:500] to inspect it."
        )

    draws.sort(key=lambda d: (d["draw_date"], d["draw_time"]))  # ascending, oldest first

    output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "state": "va",
        "note": "VA Pick 3, full history as returned by the Virginia Lottery API. Fireball included for both draws.",
        "draws": draws,
    }

    os.makedirs("data/pick3", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(draws)} draws to {OUTPUT_PATH}")
    print(f"Latest: {draws[-1]['draw_date']} {draws[-1]['draw_time']} - {draws[-1]['digits']} (FB {draws[-1]['fireball']})")


if __name__ == "__main__":
    main()

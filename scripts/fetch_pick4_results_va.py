"""
Pulls Virginia Pick 4 drawing history from the Virginia Lottery's own
public API - same endpoint family as the Pick 3 script, different
gameId.

Endpoint: https://www.valottery.com/api/v1/downloadall?gameId=1040
CONFIRMED working this session - real response text seen directly:
  Results for Pick 4
  5/22/2025; Day: 8,4,0,2; Fireball: 5; Night: 2,2,3,8; Fireball: 8
  5/21/2025; Day: 0,3,7,3; Fireball: 2; Night: 3,7,7,6; Fireball: 4
  ...
Same shape as Pick 3's gameId=1050 response, just 4 digits per draw
instead of 3. Not a guess - this is the actual format.

Writes data/pick4/va-history.json in the shape pick4-stats.js expects:
  { updated_at, state: "va", draws: [
      { draw_date, draw_time: "midday"|"evening", digits: [th,h,t,o], fireball: N }
  ]}
VA's "Day" drawing maps to draw_time "midday" and "Night" maps to
"evening", matching the Pick 3 script's convention.

Run on a schedule via .github/workflows/update-pick4-va.yml, same
cadence as update-pick3-va.yml (VA draws Pick 4 twice daily).
"""

import os
import re
import json
import datetime
import requests

API_URL = "https://www.valottery.com/api/v1/downloadall?gameId=1040"
OUTPUT_PATH = "data/pick4/va-history.json"

# Matches: 5/22/2025; Day: 8,4,0,2; Fireball: 5; Night: 2,2,3,8; Fireball: 8
LINE_PATTERN = re.compile(
    r"(\d{1,2})/(\d{1,2})/(\d{4});\s*"
    r"Day:\s*(\d),(\d),(\d),(\d);\s*Fireball:\s*(\d);\s*"
    r"Night:\s*(\d),(\d),(\d),(\d);\s*Fireball:\s*(\d)"
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
            continue  # skips the "Results for Pick 4" header line and any blanks

        month, day, year = m.group(1), m.group(2), m.group(3)
        draw_date = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

        day_digits = [int(m.group(4)), int(m.group(5)), int(m.group(6)), int(m.group(7))]
        day_fireball = int(m.group(8))
        night_digits = [int(m.group(9)), int(m.group(10)), int(m.group(11)), int(m.group(12))]
        night_fireball = int(m.group(13))

        draws.append({"draw_date": draw_date, "draw_time": "midday", "digits": day_digits, "fireball": day_fireball})
        draws.append({"draw_date": draw_date, "draw_time": "evening", "digits": night_digits, "fireball": night_fireball})

    return draws


def main():
    raw_text = fetch_raw_text()
    draws = parse_lines(raw_text)

    if not draws:
        raise RuntimeError(
            "No draws parsed from the VA Pick 4 API response - the text "
            "format may have changed. Print raw_text[:500] to inspect it."
        )

    draws.sort(key=lambda d: (d["draw_date"], d["draw_time"]))

    output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "state": "va",
        "note": "VA Pick 4, full history as returned by the Virginia Lottery API. Fireball included for both draws.",
        "draws": draws,
    }

    os.makedirs("data/pick4", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(draws)} draws to {OUTPUT_PATH}")
    print(f"Latest: {draws[-1]['draw_date']} {draws[-1]['draw_time']} - {draws[-1]['digits']} (FB {draws[-1]['fireball']})")


if __name__ == "__main__":
    main()

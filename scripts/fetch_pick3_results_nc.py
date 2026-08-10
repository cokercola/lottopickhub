"""
Pulls NC Pick 3 drawing history from the North Carolina Education
Lottery's own CSV export - a real downloadable file, not a scraper
against a rendered page.

Endpoint: https://nclottery.com/pick3-download

CONFIRMED FORMAT (verified against an actual downloaded copy of the
file, not guessed):
  Header row: "Date","Day/Eve","Ball 1","Ball 2","Ball 3","Fireball","GreenBall","DoubleDraw*"
  Example row: "08/09/2026","D","5","7","4","4","",""

Notes on the columns:
  - Date is MM/DD/YYYY.
  - Day/Eve is "D" (midday) or "E" (evening).
  - Ball 1-3 are the three Pick 3 digits, in drawn order.
  - Fireball is blank ("") on older draws from before NC added the
    Fireball add-on - treated as None, matching the other states'
    scripts when a state doesn't offer Fireball on a given draw.
  - GreenBall and DoubleDraw are unrelated to Pick 3 scoring and are
    ignored here.
  - The file ends with a trailing explanatory footer row (starts with
    "*DoubleDraw Key...") that isn't a real data row - skipped by
    checking the Date field matches MM/DD/YYYY.

This endpoint returns the FULL history back to 2006 in one request
(no pagination), same as the VA API. NC does not require requests to
identify as a browser to download it.

Writes data/pick3/nc-history.json in the shape pick3-stats.js expects:
  { updated_at, state: "nc", draws: [
      { draw_date, draw_time: "midday"|"evening", digits: [h,t,o], fireball: N|null }
  ]}

Run on a schedule via .github/workflows/update-pick3-nc.yml (follow
the same pattern as update-pick3-va.yml - NC also draws twice daily).
"""

import os
import re
import csv
import io
import json
import datetime
import requests

DOWNLOAD_URL = "https://nclottery.com/pick3-download"
OUTPUT_PATH = "data/pick3/nc-history.json"

DATE_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4}$")
DRAW_TIME_MAP = {"D": "midday", "E": "evening"}

# How far back to keep - NC's file goes back to 2006, far more than
# needed for hot/cold or heatmap stats. Same reasoning as the NY
# script: keep recent history only, to avoid an ever-growing JSON file
# the browser has to fetch on every page load. Adjust freely.
KEEP_SINCE_YEARS = 2


def fetch_csv_text():
    resp = requests.get(DOWNLOAD_URL, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_csv(csv_text):
    reader = csv.reader(io.StringIO(csv_text))
    header = next(reader, None)  # skip header row

    draws = []
    for row in reader:
        if len(row) < 6:
            continue  # skips the trailing footer row and any blank lines
        date_raw, day_eve = row[0], row[1]
        if not DATE_PATTERN.match(date_raw):
            continue  # footer row's first "field" isn't a real date

        draw_time = DRAW_TIME_MAP.get(day_eve)
        if not draw_time:
            continue  # unexpected value in Day/Eve - skip rather than guess

        try:
            digits = [int(row[2]), int(row[3]), int(row[4])]
        except (ValueError, IndexError):
            continue  # malformed ball values - skip this row

        fireball_raw = row[5].strip() if len(row) > 5 else ""
        fireball = int(fireball_raw) if fireball_raw.isdigit() else None

        month, day, year = date_raw.split("/")
        draw_date = f"{year}-{month}-{day}"

        draws.append({"draw_date": draw_date, "draw_time": draw_time, "digits": digits, "fireball": fireball})

    return draws


def main():
    csv_text = fetch_csv_text()
    draws = parse_csv(csv_text)

    if not draws:
        raise RuntimeError(
            "No draws parsed from the NC CSV - the file format may have "
            "changed. Check the header row and a few sample rows."
        )

    cutoff = (datetime.date.today() - datetime.timedelta(days=365 * KEEP_SINCE_YEARS)).isoformat()
    draws = [d for d in draws if d["draw_date"] >= cutoff]

    draws.sort(key=lambda d: (d["draw_date"], d["draw_time"]))  # ascending, oldest first

    output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "state": "nc",
        "note": f"Last {KEEP_SINCE_YEARS} years of NC Pick 3 draws. Fireball is null on draws from before NC added it.",
        "draws": draws,
    }

    os.makedirs("data/pick3", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(draws)} draws to {OUTPUT_PATH}")
    print(f"Latest: {draws[-1]['draw_date']} {draws[-1]['draw_time']} - {draws[-1]['digits']} (FB {draws[-1]['fireball']})")


if __name__ == "__main__":
    main()

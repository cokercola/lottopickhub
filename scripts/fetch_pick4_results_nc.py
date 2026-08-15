"""
Pulls NC Pick 4 drawing history from the North Carolina Education
Lottery's own CSV export - same URL family as the Pick 3 script.

Endpoint: https://nclottery.com/pick4-download

CONFIRMED this session: the URL exists and returns a real file
(Content-Type: application/vnd.ms-excel), same as pick3-download.
NOT YET CONFIRMED: the exact column layout. This script assumes it
mirrors pick3-download's format with an extra ball column -
  "Date","Day/Eve","Ball 1","Ball 2","Ball 3","Ball 4","Fireball","GreenBall","DoubleDraw*"
- since that's the same lottery's export system for a near-identical
game, but that assumption hasn't been checked against real downloaded
rows the way the Pick 3 script's docstring could confirm. Run this
once manually and check the printed sample before trusting it on a
schedule; if columns are shifted, only the row-parsing indices in
parse_csv() need adjusting.

Writes data/pick4/nc-history.json in the shape pick4-stats.js expects:
  { updated_at, state: "nc", draws: [
      { draw_date, draw_time: "midday"|"evening", digits: [th,h,t,o], fireball: N|null }
  ]}

Run on a schedule via .github/workflows/update-pick4-nc.yml, same
pattern as update-pick3-nc.yml.
"""

import os
import re
import csv
import io
import json
import datetime
import requests

DOWNLOAD_URL = "https://nclottery.com/pick4-download"
OUTPUT_PATH = "data/pick4/nc-history.json"

DATE_PATTERN = re.compile(r"^\d{2}/\d{2}/\d{4}$")
DRAW_TIME_MAP = {"D": "midday", "E": "evening"}

KEEP_SINCE_YEARS = 2


def fetch_csv_text():
    resp = requests.get(DOWNLOAD_URL, timeout=30)
    resp.raise_for_status()
    return resp.text


def parse_csv(csv_text):
    reader = csv.reader(io.StringIO(csv_text))
    header = next(reader, None)
    print(f"NC Pick 4 CSV header (verify this matches the assumed layout): {header}")

    draws = []
    for row in reader:
        if len(row) < 7:
            continue  # skips the trailing footer row and any blank lines
        date_raw, day_eve = row[0], row[1]
        if not DATE_PATTERN.match(date_raw):
            continue

        draw_time = DRAW_TIME_MAP.get(day_eve)
        if not draw_time:
            continue

        try:
            digits = [int(row[2]), int(row[3]), int(row[4]), int(row[5])]
        except (ValueError, IndexError):
            continue

        fireball_raw = row[6].strip() if len(row) > 6 else ""
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
            "No draws parsed from the NC Pick 4 CSV - the column layout "
            "likely differs from the assumption in this script's docstring. "
            "Check the printed header line and adjust parse_csv()'s indices."
        )

    cutoff = (datetime.date.today() - datetime.timedelta(days=365 * KEEP_SINCE_YEARS)).isoformat()
    draws = [d for d in draws if d["draw_date"] >= cutoff]
    draws.sort(key=lambda d: (d["draw_date"], d["draw_time"]))

    output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "state": "nc",
        "note": f"Last {KEEP_SINCE_YEARS} years of NC Pick 4 draws. Fireball is null on draws from before NC added it.",
        "draws": draws,
    }

    os.makedirs("data/pick4", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(draws)} draws to {OUTPUT_PATH}")
    print(f"Latest: {draws[-1]['draw_date']} {draws[-1]['draw_time']} - {draws[-1]['digits']} (FB {draws[-1]['fireball']})")


if __name__ == "__main__":
    main()

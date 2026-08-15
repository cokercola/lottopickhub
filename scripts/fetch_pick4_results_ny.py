"""
Pulls NY Pick 4 (branded "Win 4" by NY Lottery) drawing history from
the SAME data.ny.gov dataset used by fetch_pick3_results_ny.py - the
dataset combines Numbers (Pick 3) and Win 4 in one table, this script
just reads the other pair of columns.

Dataset: "Lottery Daily Numbers/Win-4 Winning Numbers: Beginning 1980"
Endpoint: https://data.ny.gov/resource/hsys-3def.json

IMPORTANT - VERIFY BEFORE RELYING ON THIS SCRIPT, same caveat as the
Pick 3 NY script: the field names below (MIDDAY_FIELD, EVENING_FIELD)
follow Socrata's usual naming convention applied to what the catalog
page shows, but have NOT been confirmed against a live API response in
this session. Before running on a schedule:
  1. Run this script once locally / manually.
  2. If it errors or the digits look wrong, uncomment the debug print
     in fetch_all_draws() to see the raw field names Socrata actually
     returns, and fix the *_FIELD constants to match.
If fetch_pick3_results_ny.py has already been run and its field names
confirmed, check this dataset's Win 4 columns at the same time to save
a round trip - they're the same underlying records.

Writes data/pick4/ny-history.json in the shape pick4-stats.js expects:
  { updated_at, state: "ny", draws: [
      { draw_date, draw_time: "midday"|"evening", digits: [th,h,t,o], fireball: null }
  ]}
NY's Win 4 game has no Fireball-style bonus digit, so fireball is
always null - same as the Pick 3 NY script.

Run on a schedule via .github/workflows/update-pick4-ny.yml, same
pattern as update-pick3-ny.yml.
"""

import os
import json
import datetime
import requests

API_URL = "https://data.ny.gov/resource/hsys-3def.json"
OUTPUT_PATH = "data/pick4/ny-history.json"

DRAW_DATE_FIELD = "draw_date"
# Best-guess Socrata field names - VERIFY, see docstring above.
MIDDAY_FIELD = "midday_win_4"
EVENING_FIELD = "evening_win_4"

KEEP_SINCE_YEARS = 2


def fetch_all_draws():
    since = (datetime.date.today() - datetime.timedelta(days=365 * KEEP_SINCE_YEARS)).isoformat()
    params = {
        "$limit": 5000,
        "$order": f"{DRAW_DATE_FIELD} DESC",
        "$where": f"{DRAW_DATE_FIELD} >= '{since}T00:00:00.000'",
    }
    resp = requests.get(API_URL, params=params, timeout=30)
    resp.raise_for_status()
    records = resp.json()

    # Uncomment to inspect real field names if parsing comes up empty:
    # if records:
    #     print(json.dumps(records[0], indent=2))

    return records


def parse_digits(raw):
    """NY's Win 4 value is typically a 4-character string like "4721"
    (sometimes zero-padded, sometimes not). Returns None if the field
    is missing/blank."""
    if not raw:
        return None
    cleaned = str(raw).strip().zfill(4)
    if len(cleaned) != 4 or not cleaned.isdigit():
        return None
    return [int(c) for c in cleaned]


def parse_record(record):
    draw_date_raw = record.get(DRAW_DATE_FIELD)
    if not draw_date_raw:
        return []

    draw_date = draw_date_raw[:10]
    out = []

    midday_digits = parse_digits(record.get(MIDDAY_FIELD))
    if midday_digits:
        out.append({"draw_date": draw_date, "draw_time": "midday", "digits": midday_digits, "fireball": None})

    evening_digits = parse_digits(record.get(EVENING_FIELD))
    if evening_digits:
        out.append({"draw_date": draw_date, "draw_time": "evening", "digits": evening_digits, "fireball": None})

    return out


def main():
    raw_records = fetch_all_draws()

    draws = []
    for r in raw_records:
        draws.extend(parse_record(r))

    if not draws:
        raise RuntimeError(
            "No valid Win 4 draws parsed - the dataset's field names may "
            "not match MIDDAY_FIELD/EVENING_FIELD. Uncomment the debug "
            "print in fetch_all_draws() and check the raw keys."
        )

    draws.sort(key=lambda d: (d["draw_date"], d["draw_time"]))

    output = {
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "state": "ny",
        "note": f"Last {KEEP_SINCE_YEARS} years of NY Win 4 draws. NY has no Fireball-equivalent bonus digit.",
        "draws": draws,
    }

    os.makedirs("data/pick4", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(draws)} draws to {OUTPUT_PATH}")
    print(f"Latest: {draws[-1]['draw_date']} {draws[-1]['draw_time']} - {draws[-1]['digits']}")


if __name__ == "__main__":
    main()

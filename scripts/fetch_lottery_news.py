"""
Pulls recent lottery-related news headlines via GNews.io - a real,
legitimate news API with a free tier (100 requests/day, no credit
card). This replaced an earlier draft that tried to use Google News'
RSS feed directly; that endpoint is blocked by Google's own robots.txt,
so it was scrapped in favor of an actual permitted API.

NOTE: GNews's free tier is explicitly for non-commercial use. A
voluntary tip jar is a gray area, not a clear-cut commercial product -
worth revisiting (a paid GNews tier, or a commercial-friendly
alternative like Currents API) if the site grows or adds ads.

Only stores headline, source name, publish date, and a link back to
the original article - never full article text.

Required environment variable (set as a GitHub Actions secret):
  GNEWS_API_KEY - free, no credit card, from https://gnews.io/register

Run daily via .github/workflows/update-lottery-news.yml
"""

import os
import re
import json
import datetime
import requests

GNEWS_API_KEY = os.environ["GNEWS_API_KEY"]
API_URL = "https://gnews.io/api/v4/search"
QUERY = "Powerball OR \"lottery jackpot\" OR \"Mega Millions\""
OUTPUT_PATH = "data/lottery-news.json"
MAX_ITEMS = 8
FETCH_COUNT = 10  # GNews free tier's per-request cap -- same API cost as
                   # fewer, so always request the max to leave headroom
                   # for deduping without coming up short on real results

# Gannett/USA Today Network syndicates the same wire article across dozens
# of local papers (Lansing State Journal, Cincinnati Enquirer, etc.) under
# identical trailing numeric IDs in the URL, e.g. ".../91174696007/". This
# catches those even when a couple of outlets tweak the headline slightly,
# which exact-title matching alone would miss.
SYNDICATION_ID_RE = re.compile(r"/(\d{6,})/?(?:\?.*)?$")


def fetch_articles():
    params = {
        "q": QUERY,
        "lang": "en",
        "max": FETCH_COUNT,
        "apikey": GNEWS_API_KEY,
    }
    resp = requests.get(API_URL, params=params, timeout=30)
    if not resp.ok:
        print(f"GNews API error {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    return resp.json().get("articles", [])


def dedupe_articles(items):
    """
    Keeps the first-seen article for any syndication ID or exact title
    match. Order is preserved (GNews returns newest/most relevant first),
    so "first seen" is effectively "most prominent" among the duplicates.
    """
    seen_ids = set()
    seen_titles = set()
    deduped = []
    for item in items:
        id_match = SYNDICATION_ID_RE.search(item["link"])
        syndication_id = id_match.group(1) if id_match else None
        title_key = item["title"].strip().lower()

        if syndication_id and syndication_id in seen_ids:
            continue
        if title_key in seen_titles:
            continue

        if syndication_id:
            seen_ids.add(syndication_id)
        seen_titles.add(title_key)
        deduped.append(item)
    return deduped


def main():
    raw_articles = fetch_articles()

    items = []
    for a in raw_articles:
        title = a.get("title")
        url = a.get("url")
        if not title or not url:
            continue
        items.append({
            "title": title,
            "link": url,
            "source": (a.get("source") or {}).get("name", ""),
            "published": a.get("publishedAt", ""),
        })

    items = dedupe_articles(items)

    output = {
        "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "articles": items[:MAX_ITEMS],
    }

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(output['articles'])} news items to {OUTPUT_PATH} "
          f"({len(raw_articles)} fetched, {len(raw_articles) - len(items)} duplicates removed)")


if __name__ == "__main__":
    main()

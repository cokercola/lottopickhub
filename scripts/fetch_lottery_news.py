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
import json
import datetime
import requests

GNEWS_API_KEY = os.environ["GNEWS_API_KEY"]
API_URL = "https://gnews.io/api/v4/search"
QUERY = "Powerball OR \"lottery jackpot\" OR \"Mega Millions\""
OUTPUT_PATH = "data/lottery-news.json"
MAX_ITEMS = 8


def fetch_articles():
    params = {
        "q": QUERY,
        "lang": "en",
        "max": MAX_ITEMS,
        "apikey": GNEWS_API_KEY,
    }
    resp = requests.get(API_URL, params=params, timeout=30)
    if not resp.ok:
        print(f"GNews API error {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    return resp.json().get("articles", [])


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

    output = {
        "updated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "articles": items[:MAX_ITEMS],
    }

    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote {len(output['articles'])} news items to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

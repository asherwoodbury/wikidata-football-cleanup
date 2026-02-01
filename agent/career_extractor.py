#!/usr/bin/env python3
"""
AI-assisted career data extractor.

Reads Wikipedia articles for players with stale Wikidata entries
and extracts career information (club tenures with dates).
"""

import argparse
import csv
import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Wikipedia API endpoint
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"


def get_wikipedia_article(player_name: str) -> str | None:
    """Fetch Wikipedia article content for a player."""
    params = {
        "action": "query",
        "titles": player_name,
        "prop": "extracts|revisions",
        "explaintext": True,
        "rvprop": "content",
        "format": "json",
    }

    response = requests.get(
        WIKIPEDIA_API,
        params=params,
        headers={"User-Agent": "WikidataFootballCleanup/1.0"}
    )

    if response.status_code != 200:
        return None

    data = response.json()
    pages = data.get("query", {}).get("pages", {})

    for page_id, page in pages.items():
        if page_id == "-1":
            return None
        return page.get("extract", "")

    return None


def get_wikipedia_html(player_name: str) -> str | None:
    """Fetch Wikipedia article HTML for parsing career tables."""
    params = {
        "action": "parse",
        "page": player_name,
        "prop": "text",
        "format": "json",
    }

    response = requests.get(
        WIKIPEDIA_API,
        params=params,
        headers={"User-Agent": "WikidataFootballCleanup/1.0"}
    )

    if response.status_code != 200:
        return None

    data = response.json()
    return data.get("parse", {}).get("text", {}).get("*")


def parse_career_table(html: str) -> list[dict]:
    """Parse career information from Wikipedia infobox."""
    soup = BeautifulSoup(html, "html.parser")

    # Look for infobox
    infobox = soup.find("table", class_="infobox")
    if not infobox:
        return []

    careers = []

    # Look for career rows (usually labeled "Years" and "Team")
    rows = infobox.find_all("tr")
    for row in rows:
        header = row.find("th")
        if header and "career" in header.get_text().lower():
            # Found career section
            # Parse subsequent rows for club data
            pass

    # TODO: Implement more robust parsing
    # This is a stub - actual implementation would handle
    # various Wikipedia infobox formats

    return careers


def extract_career_with_ai(player_name: str, article_text: str, target_club: str) -> dict | None:
    """
    Use AI to extract career information from article text.

    This is a placeholder for Claude API integration.
    """
    # TODO: Implement Claude API call
    # Prompt would be something like:
    # "Given this Wikipedia article about {player_name}, extract when they
    # left {target_club}. Return the end date if found."

    return None


def process_player(row: dict) -> dict | None:
    """Process a single player and extract career data."""
    player_name = row["player_name"]
    target_club = row["team_name"]

    # Try to get Wikipedia article
    html = get_wikipedia_html(player_name)
    if not html:
        return {"status": "no_wikipedia", "player": player_name}

    # Try structured parsing first
    careers = parse_career_table(html)

    # Find the relevant club tenure
    for career in careers:
        if career.get("club", "").lower() == target_club.lower():
            if career.get("end_date"):
                return {
                    "status": "found",
                    "player": player_name,
                    "player_qid": row["player_qid"],
                    "team": target_club,
                    "team_qid": row["team_qid"],
                    "end_date": career["end_date"],
                    "source": f"https://en.wikipedia.org/wiki/{player_name.replace(' ', '_')}"
                }

    # Fall back to AI extraction if structured parsing fails
    article_text = get_wikipedia_article(player_name)
    if article_text:
        ai_result = extract_career_with_ai(player_name, article_text, target_club)
        if ai_result:
            return ai_result

    return {"status": "not_found", "player": player_name, "team": target_club}


def main():
    parser = argparse.ArgumentParser(description="Extract career data from Wikipedia")
    parser.add_argument("--input", required=True, help="Input CSV of stale entries")
    parser.add_argument("--output", required=True, help="Output directory for results")
    parser.add_argument("--limit", type=int, default=10, help="Max players to process")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests")
    args = parser.parse_args()

    # Read input
    with open(args.input, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Loaded {len(rows)} stale entries")
    print(f"Processing first {args.limit}...")

    # Process players
    results = []
    for i, row in enumerate(rows[:args.limit]):
        print(f"  [{i+1}/{args.limit}] {row['player_name']}...")
        result = process_player(row)
        results.append(result)
        time.sleep(args.delay)

    # Write results
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"batch_{int(time.time())}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Summary
    found = sum(1 for r in results if r.get("status") == "found")
    no_wiki = sum(1 for r in results if r.get("status") == "no_wikipedia")
    not_found = sum(1 for r in results if r.get("status") == "not_found")

    print(f"\nResults written to {output_file}")
    print(f"  Found end date: {found}")
    print(f"  No Wikipedia: {no_wiki}")
    print(f"  Not found: {not_found}")


if __name__ == "__main__":
    main()

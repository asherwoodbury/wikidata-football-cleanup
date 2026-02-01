#!/usr/bin/env python3
"""
Fetch Wikipedia articles for players with stale Wikidata entries.

This script runs async (overnight) and saves raw article data locally.
No AI/API calls - just Wikipedia fetching.

Usage:
    python scripts/fetch_wikipedia.py --input data/stale_entries.csv --output data/wikipedia_articles/

    # With limits for testing:
    python scripts/fetch_wikipedia.py --input data/stale_entries.csv --output data/wikipedia_articles/ --limit 100

    # Resume from where you left off:
    python scripts/fetch_wikipedia.py --input data/stale_entries.csv --output data/wikipedia_articles/ --resume
"""

import argparse
import csv
import json
import os
import re
import time
import urllib.parse
from pathlib import Path
from datetime import datetime

import requests

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "WikidataFootballCleanup/1.0 (https://github.com/yourusername/wikidata-football-cleanup)"

# Rate limiting: Wikipedia asks for no more than 200 requests/second for API
# We'll be conservative: 1 request per second
REQUEST_DELAY = 1.0


def fetch_article_by_title(title: str) -> dict | None:
    """Fetch Wikipedia article by exact title."""
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts|revisions|info",
        "explaintext": True,
        "rvprop": "timestamp",
        "inprop": "url",
        "format": "json",
    }

    try:
        response = requests.get(
            WIKIPEDIA_API,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        pages = data.get("query", {}).get("pages", {})
        for page_id, page in pages.items():
            if page_id == "-1":
                return None
            return {
                "page_id": page_id,
                "title": page.get("title"),
                "url": page.get("fullurl"),
                "extract": page.get("extract", ""),
                "last_revision": page.get("revisions", [{}])[0].get("timestamp"),
                "fetched_at": datetime.utcnow().isoformat(),
            }
    except Exception as e:
        print(f"    Error fetching '{title}': {e}")
        return None

    return None


def search_wikipedia(query: str, limit: int = 3) -> list[str]:
    """Search Wikipedia and return potential article titles."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
    }

    try:
        response = requests.get(
            WIKIPEDIA_API,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        results = data.get("query", {}).get("search", [])
        return [r["title"] for r in results]
    except Exception as e:
        print(f"    Search error for '{query}': {e}")
        return []


def generate_title_variations(name: str) -> list[str]:
    """Generate possible Wikipedia article title variations for a player name."""
    variations = []

    # Exact name
    variations.append(name)

    # With (footballer) suffix
    variations.append(f"{name} (footballer)")

    # With nationality variations (common pattern)
    # e.g., "Fabio (footballer, born 1990)"

    # Replace spaces with underscores (Wikipedia style)
    underscore_name = name.replace(" ", "_")
    if underscore_name != name:
        variations.append(underscore_name)

    return variations


def fetch_player_article(player_name: str, player_qid: str) -> dict:
    """
    Try to fetch Wikipedia article for a player.
    Tries multiple title variations and search as fallback.
    """
    result = {
        "player_name": player_name,
        "player_qid": player_qid,
        "status": "not_found",
        "article": None,
        "attempted_titles": [],
        "fetched_at": datetime.utcnow().isoformat(),
    }

    # Try title variations
    for title in generate_title_variations(player_name):
        result["attempted_titles"].append(title)
        article = fetch_article_by_title(title)
        if article and len(article.get("extract", "")) > 100:
            result["status"] = "found"
            result["article"] = article
            return result
        time.sleep(REQUEST_DELAY / 2)  # Shorter delay for variations

    # Fallback: search Wikipedia
    search_query = f"{player_name} footballer"
    search_results = search_wikipedia(search_query)

    for title in search_results:
        if title not in result["attempted_titles"]:
            result["attempted_titles"].append(title)
            article = fetch_article_by_title(title)
            if article and len(article.get("extract", "")) > 100:
                # Verify it's likely the right person by checking if name appears
                extract_lower = article.get("extract", "").lower()
                name_parts = player_name.lower().split()
                if any(part in extract_lower for part in name_parts if len(part) > 2):
                    result["status"] = "found"
                    result["article"] = article
                    return result
            time.sleep(REQUEST_DELAY / 2)

    return result


def load_progress(output_dir: Path) -> set[str]:
    """Load set of already-fetched player QIDs."""
    fetched = set()
    for f in output_dir.glob("*.json"):
        try:
            with open(f) as fp:
                data = json.load(fp)
                if "player_qid" in data:
                    fetched.add(data["player_qid"])
        except:
            pass
    return fetched


def main():
    parser = argparse.ArgumentParser(description="Fetch Wikipedia articles for players")
    parser.add_argument("--input", required=True, help="Input CSV of stale entries")
    parser.add_argument("--output", required=True, help="Output directory for articles")
    parser.add_argument("--limit", type=int, default=0, help="Max players to fetch (0 = all)")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY, help="Delay between requests")
    parser.add_argument("--resume", action="store_true", help="Skip already-fetched players")
    parser.add_argument("--era", help="Only fetch players from specific era (e.g., '2018-2021')")
    args = parser.parse_args()

    # Setup output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load already-fetched players if resuming
    fetched_qids = set()
    if args.resume:
        fetched_qids = load_progress(output_dir)
        print(f"Resuming: {len(fetched_qids)} players already fetched")

    # Read input
    with open(args.input, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Filter by era if specified
    if args.era:
        rows = [r for r in rows if r.get("era") == args.era]
        print(f"Filtered to {len(rows)} players in era {args.era}")

    # Get unique players (avoid fetching same player multiple times for different clubs)
    seen_qids = set()
    unique_players = []
    for row in rows:
        qid = row["player_qid"]
        if qid not in seen_qids and qid not in fetched_qids:
            seen_qids.add(qid)
            unique_players.append(row)

    print(f"Found {len(unique_players)} unique players to fetch")

    # Apply limit
    if args.limit > 0:
        unique_players = unique_players[:args.limit]
        print(f"Limited to {len(unique_players)} players")

    # Fetch articles
    stats = {"found": 0, "not_found": 0, "errors": 0}
    start_time = time.time()

    for i, row in enumerate(unique_players):
        player_name = row["player_name"]
        player_qid = row["player_qid"]

        # Progress
        elapsed = time.time() - start_time
        rate = (i + 1) / elapsed if elapsed > 0 else 0
        eta = (len(unique_players) - i - 1) / rate if rate > 0 else 0
        print(f"[{i+1}/{len(unique_players)}] {player_name} (ETA: {eta/60:.1f}min)")

        # Fetch
        result = fetch_player_article(player_name, player_qid)

        # Add club info from the original row
        result["stale_club"] = row.get("team_name")
        result["stale_club_qid"] = row.get("team_qid")
        result["stale_start_date"] = row.get("start_date")
        result["era"] = row.get("era")

        # Save to file
        output_file = output_dir / f"{player_qid}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        # Update stats
        if result["status"] == "found":
            stats["found"] += 1
            print(f"    ✓ Found: {result['article']['title']}")
        else:
            stats["not_found"] += 1
            print(f"    ✗ Not found (tried: {result['attempted_titles']})")

        # Rate limit
        time.sleep(args.delay)

    # Summary
    elapsed = time.time() - start_time
    print(f"\n{'='*50}")
    print(f"Completed in {elapsed/60:.1f} minutes")
    print(f"  Found: {stats['found']}")
    print(f"  Not found: {stats['not_found']}")
    print(f"  Success rate: {stats['found']/(stats['found']+stats['not_found'])*100:.1f}%")
    print(f"\nArticles saved to: {output_dir}")


if __name__ == "__main__":
    main()

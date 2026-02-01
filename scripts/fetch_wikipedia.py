#!/usr/bin/env python3
"""
Fetch Wikipedia articles for players with stale Wikidata entries.

This script runs async (overnight) and saves raw article data locally.
No AI/API calls - just Wikipedia fetching.

Features:
- Automatically resumes from where it left off (incremental by default)
- Atomic file writes (no corrupted files on crash)
- Retry logic with exponential backoff
- Progress caching for fast resume
- Periodic checkpoints

Usage:
    python scripts/fetch_wikipedia.py --input data/stale_entries.csv --output data/wikipedia_articles/

    # With limits for testing:
    python scripts/fetch_wikipedia.py --input data/stale_entries.csv --output data/wikipedia_articles/ --limit 100

    # Filter by era:
    python scripts/fetch_wikipedia.py --input data/stale_entries.csv --output data/wikipedia_articles/ --era "2018-2021"

    # Force re-fetch (ignore cache):
    python scripts/fetch_wikipedia.py --input data/stale_entries.csv --output data/wikipedia_articles/ --no-resume
"""

import argparse
import csv
import json
import time
from pathlib import Path
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configuration constants
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "WikidataFootballCleanup/1.0 (https://github.com/yourusername/wikidata-football-cleanup)"
REQUEST_DELAY = 1.0  # seconds between requests
MIN_ARTICLE_LENGTH = 100  # minimum characters for valid article
SEARCH_RESULT_LIMIT = 3  # how many search results to check
CHECKPOINT_INTERVAL = 50  # save checkpoint every N players


def get_session_with_retry() -> requests.Session:
    """Create a requests session with automatic retry logic."""
    session = requests.Session()

    # Retry on connection errors, timeouts, and 500-series errors
    retry_strategy = Retry(
        total=3,
        backoff_factor=2,  # 2, 4, 8 seconds
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )

    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session


# Create session once at module level
_session = get_session_with_retry()


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
        response = _session.get(
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
    except requests.exceptions.Timeout:
        print(f"    Timeout fetching '{title}'")
        return None
    except requests.exceptions.ConnectionError as e:
        print(f"    Connection error for '{title}': {e}")
        return None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return None  # Page not found is expected
        print(f"    HTTP error {e.response.status_code} for '{title}'")
        return None
    except json.JSONDecodeError as e:
        print(f"    Invalid JSON response for '{title}': {e}")
        return None
    except Exception as e:
        print(f"    Unexpected error fetching '{title}': {type(e).__name__}: {e}")
        return None

    return None


def fetch_article_batch(titles: list[str]) -> dict[str, dict]:
    """Fetch multiple articles in one API call (more efficient)."""
    if not titles:
        return {}

    # Wikipedia API accepts pipe-separated titles (max 50)
    params = {
        "action": "query",
        "titles": "|".join(titles[:50]),
        "prop": "extracts|revisions|info",
        "explaintext": True,
        "rvprop": "timestamp",
        "inprop": "url",
        "format": "json",
    }

    try:
        response = _session.get(
            WIKIPEDIA_API,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        results = {}
        pages = data.get("query", {}).get("pages", {})
        for page_id, page in pages.items():
            if page_id != "-1" and len(page.get("extract", "")) > MIN_ARTICLE_LENGTH:
                title = page.get("title")
                results[title] = {
                    "page_id": page_id,
                    "title": title,
                    "url": page.get("fullurl"),
                    "extract": page.get("extract", ""),
                    "last_revision": page.get("revisions", [{}])[0].get("timestamp"),
                    "fetched_at": datetime.utcnow().isoformat(),
                }
        return results
    except Exception as e:
        print(f"    Batch fetch error: {e}")
        return {}


def search_wikipedia(query: str, limit: int = SEARCH_RESULT_LIMIT) -> list[str]:
    """Search Wikipedia and return potential article titles."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
    }

    try:
        response = _session.get(
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


def get_wikipedia_title_from_wikidata(qid: str) -> str | None:
    """Get the English Wikipedia article title directly from Wikidata.

    This is the most reliable method since we already have the Wikidata QID.
    Handles special characters (ñ, ö, etc.) correctly.
    """
    params = {
        "action": "wbgetentities",
        "ids": qid,
        "props": "sitelinks",
        "sitefilter": "enwiki",
        "format": "json",
    }

    try:
        response = _session.get(
            "https://www.wikidata.org/w/api.php",
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        entity = data.get("entities", {}).get(qid, {})
        sitelinks = entity.get("sitelinks", {})
        enwiki = sitelinks.get("enwiki", {})
        return enwiki.get("title")
    except Exception as e:
        # Silently fail - we'll fall back to name-based search
        return None


def generate_title_variations(name: str) -> list[str]:
    """Generate possible Wikipedia article title variations for a player name."""
    variations = []

    # Exact name
    variations.append(name)

    # With (footballer) suffix
    variations.append(f"{name} (footballer)")

    # Replace spaces with underscores (Wikipedia style)
    underscore_name = name.replace(" ", "_")
    if underscore_name != name:
        variations.append(underscore_name)

    return variations


def fetch_player_article(player_name: str, player_qid: str) -> dict:
    """
    Try to fetch Wikipedia article for a player.

    Strategy:
    1. First, ask Wikidata for the exact Wikipedia title (handles special chars like ñ, ö)
    2. Fall back to name-based title variations
    3. Fall back to Wikipedia search
    """
    result = {
        "player_name": player_name,
        "player_qid": player_qid,
        "status": "not_found",
        "article": None,
        "attempted_titles": [],
        "fetched_at": datetime.utcnow().isoformat(),
    }

    # Strategy 1: Get exact title from Wikidata (most reliable)
    wikidata_title = get_wikipedia_title_from_wikidata(player_qid)
    if wikidata_title:
        result["attempted_titles"].append(f"[wikidata] {wikidata_title}")
        article = fetch_article_by_title(wikidata_title)
        if article and len(article.get("extract", "")) > MIN_ARTICLE_LENGTH:
            result["status"] = "found"
            result["article"] = article
            return result

    # Strategy 2: Try name-based title variations
    title_variations = generate_title_variations(player_name)
    result["attempted_titles"].extend(title_variations)

    # Try to fetch all variations in one API call
    batch_results = fetch_article_batch(title_variations)

    for title in title_variations:
        if title in batch_results:
            result["status"] = "found"
            result["article"] = batch_results[title]
            return result

    time.sleep(REQUEST_DELAY / 2)

    # Fallback: search Wikipedia
    search_query = f"{player_name} footballer"
    search_results = search_wikipedia(search_query)

    if search_results:
        # Batch fetch search results
        new_titles = [t for t in search_results if t not in result["attempted_titles"]]
        result["attempted_titles"].extend(new_titles)

        if new_titles:
            batch_results = fetch_article_batch(new_titles)

            for title in new_titles:
                if title in batch_results:
                    article = batch_results[title]
                    # Verify it's likely the right person
                    extract_lower = article.get("extract", "").lower()
                    name_parts = player_name.lower().split()
                    if any(part in extract_lower for part in name_parts if len(part) > 2):
                        result["status"] = "found"
                        result["article"] = article
                        return result

    return result


def load_progress(output_dir: Path) -> set[str]:
    """Load set of already-fetched player QIDs from cache or directory scan."""
    progress_cache = output_dir / ".progress_cache.txt"
    fetched = set()

    # Try to load from cache first (fast path)
    if progress_cache.exists():
        try:
            with open(progress_cache, 'r') as f:
                cached_qids = set(line.strip() for line in f if line.strip())
            print(f"  Loaded {len(cached_qids)} QIDs from cache")

            # Verify cache is still valid by checking a few files exist
            sample_qids = list(cached_qids)[:min(5, len(cached_qids))]
            if all((output_dir / f"{qid}.json").exists() for qid in sample_qids):
                return cached_qids
            else:
                print(f"  Cache validation failed, rebuilding...")
        except Exception as e:
            print(f"  Cache read error: {e}, rebuilding...")

    # Slow path: scan directory
    print(f"  Scanning {output_dir} for fetched articles...")
    for f in output_dir.glob("*.json"):
        try:
            # Quick validation: check file is non-empty
            if f.stat().st_size < 10:
                print(f"    Warning: {f.name} is suspiciously small, skipping")
                continue

            with open(f) as fp:
                data = json.load(fp)
                if "player_qid" in data and "status" in data:
                    fetched.add(data["player_qid"])
                else:
                    print(f"    Warning: {f.name} missing required fields, skipping")
        except json.JSONDecodeError as e:
            print(f"    Error: {f.name} is corrupted ({e}), skipping")
        except Exception as e:
            print(f"    Error reading {f.name}: {e}")

    # Write cache for next time
    save_progress_cache(output_dir, fetched)

    return fetched


def save_progress_cache(output_dir: Path, fetched_qids: set[str]):
    """Save progress cache for fast resume."""
    progress_cache = output_dir / ".progress_cache.txt"
    try:
        with open(progress_cache, 'w') as f:
            f.write('\n'.join(sorted(fetched_qids)))
        print(f"  Cached {len(fetched_qids)} QIDs for faster resume")
    except Exception as e:
        print(f"  Warning: Could not write cache: {e}")


def save_checkpoint(output_dir: Path, stats: dict, processed_count: int, total_count: int):
    """Save progress checkpoint with stats."""
    checkpoint_file = output_dir / ".checkpoint.json"
    try:
        with open(checkpoint_file, 'w') as f:
            json.dump({
                "stats": stats,
                "processed_count": processed_count,
                "total_count": total_count,
                "timestamp": datetime.utcnow().isoformat()
            }, f, indent=2)
    except Exception as e:
        print(f"Warning: Could not save checkpoint: {e}")


def save_result_atomically(output_dir: Path, player_qid: str, result: dict) -> bool:
    """Save result to file atomically (prevents corruption on crash)."""
    output_file = output_dir / f"{player_qid}.json"
    temp_file = output_dir / f".{player_qid}.json.tmp"

    try:
        # Write to temp file first
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        # Atomic rename
        temp_file.rename(output_file)
        return True
    except Exception as e:
        print(f"    Error saving {player_qid}: {e}")
        if temp_file.exists():
            temp_file.unlink()
        return False


def main():
    parser = argparse.ArgumentParser(description="Fetch Wikipedia articles for players")
    parser.add_argument("--input", required=True, help="Input CSV of stale entries")
    parser.add_argument("--output", required=True, help="Output directory for articles")
    parser.add_argument("--limit", type=int, default=0, help="Max players to fetch (0 = all)")
    parser.add_argument("--delay", type=float, default=REQUEST_DELAY, help="Delay between requests")
    parser.add_argument("--no-resume", action="store_true", help="Ignore existing progress, start fresh")
    parser.add_argument("--era", help="Only fetch players from specific era (e.g., '2018-2021')")
    args = parser.parse_args()

    # Setup output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load already-fetched players (automatic resume by default)
    fetched_qids = set()
    if not args.no_resume:
        print("Checking for existing progress...")
        fetched_qids = load_progress(output_dir)
        if fetched_qids:
            print(f"Resuming: {len(fetched_qids)} players already fetched")
    else:
        print("Starting fresh (--no-resume specified)")

    # Read input
    with open(args.input, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Filter by era if specified
    if args.era:
        rows = [r for r in rows if r.get("era") == args.era]
        print(f"Filtered to {len(rows)} entries in era {args.era}")

    # Get unique players (avoid fetching same player multiple times for different clubs)
    seen_qids = set()
    unique_players = []
    for row in rows:
        qid = row["player_qid"]
        if qid not in seen_qids and qid not in fetched_qids:
            seen_qids.add(qid)
            unique_players.append(row)

    print(f"Found {len(unique_players)} unique players to fetch")

    if not unique_players:
        print("Nothing to do!")
        return

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

        # Progress with ETA
        elapsed = time.time() - start_time
        completed = i + 1

        if completed > 1:
            avg_time_per_player = elapsed / completed
            remaining = len(unique_players) - completed
            eta_seconds = avg_time_per_player * remaining
            eta_str = f"{eta_seconds/60:.1f}min" if eta_seconds > 60 else f"{eta_seconds:.0f}s"
        else:
            eta_str = "calculating..."

        print(f"[{completed}/{len(unique_players)}] {player_name}")
        print(f"  Progress: {completed/len(unique_players)*100:.1f}% | ETA: {eta_str}")

        # Fetch
        result = fetch_player_article(player_name, player_qid)

        # Add club info from the original row
        result["stale_club"] = row.get("team_name")
        result["stale_club_qid"] = row.get("team_qid")
        result["stale_start_date"] = row.get("start_date")
        result["era"] = row.get("era")

        # Save atomically
        if save_result_atomically(output_dir, player_qid, result):
            fetched_qids.add(player_qid)

            # Update stats
            if result["status"] == "found":
                stats["found"] += 1
                print(f"  ✓ Found: {result['article']['title']}")
            else:
                stats["not_found"] += 1
                print(f"  ✗ Not found (tried: {result['attempted_titles'][:3]}...)")
        else:
            stats["errors"] += 1

        # Periodic checkpoint
        if completed % CHECKPOINT_INTERVAL == 0:
            save_progress_cache(output_dir, fetched_qids)
            save_checkpoint(output_dir, stats, completed, len(unique_players))
            print(f"  [Checkpoint saved]")

        # Rate limit
        time.sleep(args.delay)

    # Final save
    save_progress_cache(output_dir, fetched_qids)
    save_checkpoint(output_dir, stats, len(unique_players), len(unique_players))

    # Summary
    elapsed = time.time() - start_time
    print(f"\n{'='*50}")
    print(f"Completed in {elapsed/60:.1f} minutes")
    print(f"  Found: {stats['found']}")
    print(f"  Not found: {stats['not_found']}")
    print(f"  Errors: {stats['errors']}")
    if stats['found'] + stats['not_found'] > 0:
        print(f"  Success rate: {stats['found']/(stats['found']+stats['not_found'])*100:.1f}%")
    print(f"\nArticles saved to: {output_dir}")


if __name__ == "__main__":
    main()

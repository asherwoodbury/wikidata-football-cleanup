#!/usr/bin/env python3
"""
Summarize fetched Wikipedia articles.

Run this after fetch_wikipedia.py to see stats and prepare for Claude processing.

Usage:
    python scripts/summarize_fetched.py --input data/wikipedia_articles/
"""

import argparse
import json
from pathlib import Path
from collections import Counter


def main():
    parser = argparse.ArgumentParser(description="Summarize fetched Wikipedia articles")
    parser.add_argument("--input", required=True, help="Directory with fetched articles")
    parser.add_argument("--output", help="Output CSV for Claude processing")
    args = parser.parse_args()

    input_dir = Path(args.input)
    if not input_dir.exists():
        print(f"Error: {input_dir} does not exist")
        return

    # Load all fetched articles
    articles = []
    for f in input_dir.glob("*.json"):
        try:
            with open(f) as fp:
                data = json.load(fp)
                articles.append(data)
        except Exception as e:
            print(f"Error loading {f}: {e}")

    print(f"Loaded {len(articles)} fetched articles\n")

    # Stats by status
    status_counts = Counter(a["status"] for a in articles)
    print("Status breakdown:")
    for status, count in status_counts.most_common():
        print(f"  {status}: {count}")

    # Stats by era
    found_articles = [a for a in articles if a["status"] == "found"]
    era_counts = Counter(a.get("era", "unknown") for a in found_articles)
    print(f"\nFound articles by era:")
    for era, count in sorted(era_counts.items()):
        print(f"  {era}: {count}")

    # Article length distribution
    lengths = [len(a["article"]["extract"]) for a in found_articles]
    if lengths:
        print(f"\nArticle length stats:")
        print(f"  Min: {min(lengths):,} chars")
        print(f"  Max: {max(lengths):,} chars")
        print(f"  Avg: {sum(lengths)//len(lengths):,} chars")

    # Sample of found articles
    print(f"\nSample of found articles:")
    for a in found_articles[:5]:
        title = a["article"]["title"]
        club = a.get("stale_club", "?")
        length = len(a["article"]["extract"])
        print(f"  {a['player_name']} ({club}) - {length:,} chars")

    # Sample of not found
    not_found = [a for a in articles if a["status"] == "not_found"]
    if not_found:
        print(f"\nSample of NOT found:")
        for a in not_found[:5]:
            print(f"  {a['player_name']} - tried: {a.get('attempted_titles', [])[:2]}")

    # Prepare for Claude processing
    if args.output:
        import csv
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["player_qid", "player_name", "stale_club", "stale_club_qid",
                           "start_date", "era", "article_file", "article_length"])
            for a in found_articles:
                writer.writerow([
                    a["player_qid"],
                    a["player_name"],
                    a.get("stale_club", ""),
                    a.get("stale_club_qid", ""),
                    a.get("stale_start_date", ""),
                    a.get("era", ""),
                    f"{a['player_qid']}.json",
                    len(a["article"]["extract"])
                ])
        print(f"\nWrote {len(found_articles)} entries to {args.output}")
        print("This file is ready for Claude processing!")


if __name__ == "__main__":
    main()

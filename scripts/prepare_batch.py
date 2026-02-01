#!/usr/bin/env python3
"""
Prepare a batch of articles for Claude processing.

Extracts article text and formats it for easy reading/processing.

Usage:
    # Prepare 50 articles for processing
    python scripts/prepare_batch.py --input data/wikipedia_articles/ --output data/batches/batch_001.txt --limit 50

    # Prepare specific era
    python scripts/prepare_batch.py --input data/wikipedia_articles/ --output data/batches/batch_001.txt --era "2018-2021" --limit 50
"""

import argparse
import json
from pathlib import Path


def extract_career_section(text: str) -> str:
    """Extract the Club career section from Wikipedia article text."""
    # Look for career section headers
    career_markers = [
        "== Club career ==",
        "== Career ==",
        "== Professional career ==",
        "== Playing career ==",
    ]

    text_lower = text.lower()
    start_idx = -1

    for marker in career_markers:
        idx = text_lower.find(marker.lower())
        if idx != -1:
            start_idx = idx
            break

    if start_idx == -1:
        # No career section found, return first part of article
        return text[:5000]

    # Find the end of the career section (next major section)
    career_text = text[start_idx:]

    # Look for next major section (== Something ==)
    end_markers = [
        "\n== International",
        "\n== Personal",
        "\n== Honours",
        "\n== Career statistics",
        "\n== References",
        "\n== External",
        "\n== Style",
        "\n== Playing style",
    ]

    end_idx = len(career_text)
    for marker in end_markers:
        idx = career_text.lower().find(marker.lower())
        if idx != -1 and idx < end_idx:
            end_idx = idx

    return career_text[:end_idx]


def main():
    parser = argparse.ArgumentParser(description="Prepare batch for Claude processing")
    parser.add_argument("--input", required=True, help="Directory with fetched articles")
    parser.add_argument("--output", required=True, help="Output text file for batch")
    parser.add_argument("--limit", type=int, default=50, help="Number of articles in batch")
    parser.add_argument("--era", help="Filter by era")
    parser.add_argument("--skip", type=int, default=0, help="Skip first N articles")
    args = parser.parse_args()

    input_dir = Path(args.input)
    output_file = Path(args.output)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Load articles
    articles = []
    for f in sorted(input_dir.glob("*.json")):
        try:
            with open(f) as fp:
                data = json.load(fp)
                if data["status"] == "found":
                    if args.era and data.get("era") != args.era:
                        continue
                    articles.append(data)
        except:
            pass

    print(f"Found {len(articles)} articles with status='found'")

    # Apply skip and limit
    articles = articles[args.skip:args.skip + args.limit]
    print(f"Processing {len(articles)} articles (skip={args.skip}, limit={args.limit})")

    # Generate batch file
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# Wikipedia Articles Batch for Claude Processing\n")
        f.write(f"# Generated: {__import__('datetime').datetime.now().isoformat()}\n")
        f.write(f"# Total articles: {len(articles)}\n")
        f.write(f"# Era filter: {args.era or 'none'}\n")
        f.write("\n" + "="*80 + "\n\n")

        for i, article in enumerate(articles):
            player_name = article["player_name"]
            player_qid = article["player_qid"]
            stale_club = article.get("stale_club", "Unknown")
            stale_club_qid = article.get("stale_club_qid", "")
            start_date = article.get("stale_start_date", "")
            wiki_url = article["article"].get("url", "")

            # Extract career section
            full_text = article["article"]["extract"]
            career_text = extract_career_section(full_text)

            f.write(f"## PLAYER {i+1}: {player_name}\n")
            f.write(f"QID: {player_qid}\n")
            f.write(f"Stale Club: {stale_club} ({stale_club_qid})\n")
            f.write(f"Start Date: {start_date}\n")
            f.write(f"Wikipedia: {wiki_url}\n")
            f.write(f"\n### Career Section:\n\n")
            f.write(career_text)
            f.write(f"\n\n{'='*80}\n\n")

    print(f"\nBatch written to: {output_file}")
    print(f"File size: {output_file.stat().st_size / 1024:.1f} KB")
    print("\nTo process with Claude:")
    print(f"  1. Open Claude Code in ~/git/wikidata-football-cleanup")
    print(f"  2. Ask: 'Read {output_file} and extract end dates for each player'")


if __name__ == "__main__":
    main()

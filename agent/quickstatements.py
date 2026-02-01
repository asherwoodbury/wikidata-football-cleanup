#!/usr/bin/env python3
"""
Generate QuickStatements commands for Wikidata corrections.

Takes reviewed corrections and outputs QuickStatements v1 format
that can be pasted into https://quickstatements.toolforge.org/
"""

import argparse
import csv
import json
from datetime import datetime


def parse_date(date_str: str) -> tuple[str, int]:
    """
    Parse a date string and return Wikidata format with precision.

    Returns: (wikidata_date, precision)
    - precision 11 = day
    - precision 10 = month
    - precision 9 = year
    """
    date_str = date_str.strip()

    # Try full date (YYYY-MM-DD)
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return f"+{dt.strftime('%Y-%m-%dT00:00:00Z')}", 11
    except ValueError:
        pass

    # Try year-month (YYYY-MM)
    try:
        dt = datetime.strptime(date_str, "%Y-%m")
        return f"+{dt.strftime('%Y-%m-00T00:00:00Z')}", 10
    except ValueError:
        pass

    # Try year only (YYYY)
    try:
        year = int(date_str)
        if 1900 <= year <= 2100:
            return f"+{year}-00-00T00:00:00Z", 9
    except ValueError:
        pass

    raise ValueError(f"Cannot parse date: {date_str}")


def generate_quickstatement(correction: dict) -> str | None:
    """
    Generate a QuickStatements command for a single correction.

    Format: PLAYER_QID<TAB>P54<TAB>TEAM_QID<TAB>P582<TAB>END_DATE

    This adds an end time (P582) qualifier to an existing P54 claim.
    """
    if correction.get("status") != "found":
        return None

    try:
        end_date, precision = parse_date(correction["end_date"])
    except ValueError as e:
        print(f"  Skipping {correction['player']}: {e}")
        return None

    player_qid = correction["player_qid"]
    team_qid = correction["team_qid"]
    source_url = correction.get("source", "")

    # QuickStatements format for adding qualifier to existing claim
    # Note: This assumes the P54 claim already exists
    # Format: Qxxx|P54|Qyyy|P582|+YYYY-MM-DDT00:00:00Z/precision
    qs_line = f"{player_qid}\tP54\t{team_qid}\tP582\t{end_date}/{precision}"

    # Add reference if available
    if source_url:
        # S854 = reference URL
        # S813 = retrieved date
        today = datetime.now().strftime("+%Y-%m-%dT00:00:00Z")
        qs_line += f"\tS854\t\"{source_url}\"\tS813\t{today}/11"

    return qs_line


def main():
    parser = argparse.ArgumentParser(description="Generate QuickStatements commands")
    parser.add_argument("--input", required=True, help="Input JSON with corrections")
    parser.add_argument("--output", required=True, help="Output file for QuickStatements")
    args = parser.parse_args()

    # Read corrections
    with open(args.input, encoding="utf-8") as f:
        corrections = json.load(f)

    print(f"Loaded {len(corrections)} corrections")

    # Generate QuickStatements
    commands = []
    for correction in corrections:
        cmd = generate_quickstatement(correction)
        if cmd:
            commands.append(cmd)

    print(f"Generated {len(commands)} QuickStatements commands")

    # Write output
    with open(args.output, "w", encoding="utf-8") as f:
        for cmd in commands:
            f.write(cmd + "\n")

    print(f"Wrote commands to {args.output}")
    print("\nTo apply these corrections:")
    print("1. Go to https://quickstatements.toolforge.org/")
    print("2. Log in with your Wikidata account")
    print("3. Paste the contents of the output file")
    print("4. Add edit summary: 'Adding end date from Wikipedia (AI-assisted, human-reviewed)'")
    print("5. Review and submit")


if __name__ == "__main__":
    main()

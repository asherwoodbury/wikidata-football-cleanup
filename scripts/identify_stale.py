#!/usr/bin/env python3
"""
Identify stale player-club associations in Wikidata.

A stale association is one where:
- There is a start date but no end date
- The start date is before 2022
- It's a club team (not national team)
"""

import csv
from datetime import datetime
from SPARQLWrapper import SPARQLWrapper, JSON

WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"

QUERY = """
SELECT ?player ?playerLabel ?playerId ?team ?teamLabel ?teamId ?startTime
WHERE {
  ?player wdt:P106 wd:Q937857 .
  ?player p:P54 ?membership .
  ?membership ps:P54 ?team .
  ?membership pq:P580 ?startTime .

  FILTER NOT EXISTS { ?membership pq:P582 ?endTime }
  FILTER (?startTime < "2022-01-01"^^xsd:dateTime)
  FILTER NOT EXISTS { ?team wdt:P31 wd:Q6979593 }

  BIND(STRAFTER(STR(?player), "entity/") AS ?playerId)
  BIND(STRAFTER(STR(?team), "entity/") AS ?teamId)

  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
ORDER BY ?startTime
"""


def query_wikidata():
    """Query Wikidata for stale entries."""
    sparql = SPARQLWrapper(WIKIDATA_ENDPOINT)
    sparql.setQuery(QUERY)
    sparql.setReturnFormat(JSON)
    sparql.addCustomHttpHeader("User-Agent", "WikidataFootballCleanup/1.0")

    results = sparql.query().convert()
    return results["results"]["bindings"]


def extract_year(date_str: str) -> int:
    """Extract year from ISO date string."""
    try:
        return int(date_str[:4])
    except (ValueError, IndexError):
        return 0


def categorize_era(year: int) -> str:
    """Categorize year into era."""
    if year < 2000:
        return "pre-2000"
    elif year <= 2005:
        return "2000-2005"
    elif year <= 2010:
        return "2006-2010"
    elif year <= 2015:
        return "2011-2015"
    elif year <= 2017:
        return "2016-2017"
    elif year <= 2021:
        return "2018-2021"
    else:
        return "2022+"


def main():
    print("Querying Wikidata for stale entries...")
    results = query_wikidata()
    print(f"Found {len(results)} stale entries")

    # Write to CSV
    output_file = "data/stale_entries.csv"
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "player_qid", "player_name", "team_qid", "team_name",
            "start_date", "start_year", "era"
        ])

        for row in results:
            start_date = row["startTime"]["value"]
            start_year = extract_year(start_date)
            era = categorize_era(start_year)

            writer.writerow([
                row["playerId"]["value"],
                row["playerLabel"]["value"],
                row["teamId"]["value"],
                row["teamLabel"]["value"],
                start_date,
                start_year,
                era
            ])

    print(f"Wrote {len(results)} entries to {output_file}")

    # Print summary by era
    from collections import Counter
    eras = [categorize_era(extract_year(r["startTime"]["value"])) for r in results]
    era_counts = Counter(eras)

    print("\nSummary by era:")
    for era in sorted(era_counts.keys()):
        print(f"  {era}: {era_counts[era]}")


if __name__ == "__main__":
    main()

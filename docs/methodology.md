# Methodology

## How We Identify Stale Data

A player-club association is considered "stale" if:

1. The `member of sports team` (P54) claim has a `start time` (P580) qualifier
2. The claim does NOT have an `end time` (P582) qualifier
3. The start date is before 2022 (giving 2+ years for the data to have been updated)
4. The claim is for a club team, not a national team

### SPARQL Query

```sparql
SELECT ?player ?playerLabel ?team ?teamLabel ?startTime
WHERE {
  ?player wdt:P106 wd:Q937857 .  # occupation: association football player
  ?player p:P54 ?membership .
  ?membership ps:P54 ?team .
  ?membership pq:P580 ?startTime .
  FILTER NOT EXISTS { ?membership pq:P582 ?endTime }
  FILTER (?startTime < "2022-01-01"^^xsd:dateTime)
  FILTER NOT EXISTS { ?team wdt:P31 wd:Q6979593 }  # exclude national teams
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
```

## How We Determine Correct End Dates

### Primary Source: Wikipedia

1. **Career tables** (most reliable): Many player articles have structured tables with:
   - Club name
   - Years (e.g., "2018-2023")
   - Sometimes exact dates

2. **Infoboxes**: May contain current club and years

3. **Prose sections**: Career narrative with dates mentioned

### Extraction Priority

1. Exact end date if available (e.g., "30 June 2023")
2. Year precision if only year known (e.g., "2023")
3. Skip if ambiguous or conflicting information

## Quality Thresholds

A proposed correction is accepted if:

- ✅ Wikipedia article clearly states the player left the club
- ✅ Date is unambiguous
- ✅ Club name matches (accounting for variations)
- ❌ Reject if Wikipedia says "current" or is ambiguous
- ❌ Reject if date conflicts with other sources

## Data Precision

Wikidata supports different precision levels:

| Precision | Example | When to use |
|-----------|---------|-------------|
| Day | +2023-06-30T00:00:00Z/11 | Exact date known |
| Month | +2023-06-00T00:00:00Z/10 | Only month known |
| Year | +2023-00-00T00:00:00Z/9 | Only year known |

Most corrections will be year-precision, as Wikipedia often only states "2018-2023" without exact dates.

## Edge Cases

### Loans
- Loan spells are separate P54 claims
- Should have both start and end dates
- Parent club association continues

### Youth Teams
- Youth/reserve team stints are separate claims
- Often harder to find exact dates
- Lower priority for correction

### Multiple Stints
- Player may return to same club later
- Each stint is a separate P54 claim
- Verify which stint we're correcting

### Retired Players
- May not have explicit "left" date
- Use retirement date if clear
- Or last season mentioned

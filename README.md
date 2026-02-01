# Wikidata Football Cleanup

A community project to identify and fix stale football (soccer) player-club associations in Wikidata.

## The Problem

Wikidata contains ~47,000 football players with career history data, but many player-club associations are missing end dates. Players who joined clubs years ago still show as current squad members because Wikidata wasn't updated when they left.

### Scope

| Era | Stale Entries | Unique Players | Status |
|-----|---------------|----------------|--------|
| 2000-2005 | 246 | 224 | Pending |
| 2006-2010 | 1,125 | 1,084 | Pending |
| 2011-2015 | 7,515 | 6,947 | Pending |
| 2016-2017 | 1,757 | 1,710 | Pending |
| 2018-2021 | 2,008 | 1,912 | Pending |
| **Total** | **12,651** | **~11,900** | |

## Approach

1. **Identify stale data**: Query Wikidata for player-club associations (P54) with start dates but no end dates
2. **Research corrections**: Use Wikipedia articles (CC BY-SA) to find actual departure dates
3. **AI-assisted extraction**: Use an AI agent to read Wikipedia career tables and extract structured data
4. **Human review**: All corrections reviewed by humans before submission
5. **Submit with citations**: Use QuickStatements to add end dates with Wikipedia citations

## Why Wikipedia?

- **Legally clean**: Wikipedia is CC BY-SA, compatible with Wikidata's CC0 license
- **Good coverage**: ~95% of affected players have English Wikipedia articles
- **Citable source**: Each correction includes a Wikipedia URL as reference

## Project Structure

```
wikidata-football-cleanup/
├── agent/                    # AI agent for Wikipedia extraction
│   ├── wikipedia_reader.py   # Fetch and parse Wikipedia articles
│   ├── career_extractor.py   # Extract career data from articles
│   └── quickstatements.py    # Generate QuickStatements commands
├── data/
│   ├── stale_entries.csv     # Players needing corrections
│   ├── proposed/             # Corrections awaiting review
│   └── submitted/            # Archive of submitted batches
├── scripts/
│   ├── identify_stale.py     # Find stale Wikidata entries
│   └── validate.py           # Validate proposed corrections
└── docs/
    └── methodology.md        # How we determine correctness
```

## Getting Started

### Prerequisites

- Python 3.10+
- Wikidata account (4+ days old, 50+ edits for QuickStatements)

### Installation

```bash
git clone https://github.com/yourusername/wikidata-football-cleanup.git
cd wikidata-football-cleanup
pip install -r requirements.txt
```

### Usage

```bash
# 1. Identify stale entries (or use provided data/stale_entries.csv)
python scripts/identify_stale.py

# 2. Run AI agent to propose corrections
python agent/career_extractor.py --input data/stale_entries.csv --output data/proposed/

# 3. Review proposed corrections manually

# 4. Generate QuickStatements
python agent/quickstatements.py --input data/proposed/reviewed.csv
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
- Reviewing proposed corrections
- Submitting edits to Wikidata
- Improving the AI extraction accuracy

## Legal

- All data submitted to Wikidata must be sourced from Wikipedia or other compatible sources
- Each edit includes a citation to the source
- AI-assisted edits are disclosed per Wikipedia/Wikidata policy

## License

MIT License - see [LICENSE](LICENSE)

## Related Projects

- [1000 Soccer Players](https://github.com/yourusername/1000-soccer-players) - The trivia game that discovered this data quality issue

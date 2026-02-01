# Contributing to Wikidata Football Cleanup

Thank you for helping improve Wikidata's football data!

## Ways to Contribute

### 1. Review Proposed Corrections

The AI agent generates proposed corrections that need human review before submission.

**Review process:**
1. Check `data/proposed/` for pending corrections
2. For each correction, verify:
   - The Wikipedia article supports the end date
   - The club name matches correctly
   - No obvious errors in date parsing
3. Mark as `approved`, `rejected`, or `needs_research`

### 2. Submit Corrections to Wikidata

Once corrections are reviewed:

1. Go to [QuickStatements](https://quickstatements.toolforge.org/)
2. Log in with your Wikidata account
3. Paste the generated commands
4. Add to edit summary: `Adding end date from Wikipedia (AI-assisted, human-reviewed)`
5. Submit batch

**Requirements:**
- Wikidata account must be 4+ days old
- Must have 50+ edits on Wikidata

### 3. Improve the AI Agent

The extraction accuracy can always be improved:

- Better parsing of Wikipedia career tables
- Handle edge cases (loans, youth teams, etc.)
- Improve club name matching

### 4. Add Missing Wikipedia Articles

Some players (~5%) lack English Wikipedia articles. You can:
- Create stub articles for notable players
- Or find alternative sources (other language Wikipedias, news)

## Guidelines

### Source Requirements

All corrections must be sourced. Acceptable sources:
- ✅ English Wikipedia
- ✅ Other language Wikipedias (with translation note)
- ✅ Official club announcements
- ✅ Reliable news sources
- ❌ Transfermarkt (Terms of Service prohibit this use)
- ❌ Other commercial databases

### Edit Summary Format

Always include:
```
Adding end date (P582) to P54 claim. Source: Wikipedia. AI-assisted, human-reviewed.
```

### Batch Size

- Submit corrections in batches of 50-100
- Wait for batch to complete before submitting next
- Monitor for errors

## Code of Conduct

- Be respectful to other contributors
- Follow Wikidata's policies and guidelines
- When in doubt, ask on the Wikidata talk pages

## Questions?

Open an issue or discuss on [Wikidata:WikiProject Sports](https://www.wikidata.org/wiki/Wikidata:WikiProject_Sports).

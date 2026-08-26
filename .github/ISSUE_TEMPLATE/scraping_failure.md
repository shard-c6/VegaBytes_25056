---
name: Scraping Failure Report
about: Report when a scraper breaks, gets blocked, or returns bad data
title: '[SCRAPER] <source>: <brief description>'
labels: tier-1-data, bug
assignees: shard-c6
---

## Source
<!-- e.g. indigo_direct, makemytrip -->

## Route(s) Affected
<!-- e.g. DEL-BOM, BLR-DEL -->

## Failure Type
- [ ] IP ban / Bot detection triggered
- [ ] DOM structure changed (CSS selectors broken)
- [ ] Returns empty results (no fares shown)
- [ ] Returns incorrect/anomalous data
- [ ] Timeout / Network error

## Error Message / Log Snippet
```
paste error here
```

## Last Successful Run
<!-- Date/time of last known good scrape -->

## Attempted Fix
<!-- What did you try? Did AI DOM parser fallback also fail? -->

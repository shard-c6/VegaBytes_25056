# Demo Day Runbook — Layered Resilience Strategy

**Issue:** [#4](https://github.com/shard-c6/VegaBytes_25056/issues/4)
**Owner:** Shardul (with Rahul supporting)
**Related:** `docs/loopholes_260826.md` — Loophole 4; `docs/execution_plan_260828.md` — Track A / Shardul section

## Why this exists

The project's original backup plan was: *"if the scraper breaks on demo day, use a pre-scraped, synthetically aged Kaggle dataset."* That's transparent to any judge who asks a follow-up question, and it undermines the entire pitch — a "real-time data pipeline" whose fallback is a static third-party CSV is not a real-time data pipeline.

This runbook replaces that with three layers, each backed by something actually true: a live scrape, a database that has been genuinely collecting data since #17 shipped, and a process for recording proof as it happens. **No synthetic or third-party data is used anywhere in this pipeline or its demo strategy.** If every layer fails, the honest move is to say so and pivot the demo to the index calculation and dashboard — not to substitute fabricated data.

## Layer 1 — Live scrape (primary)

Run a live scrape against IndiGo direct during the demo — airline direct sites have weaker bot protection than OTAs, and IndiGo is the project's primary source.

```bash
# From repo root, with DATABASE_URL and GEMINI_API_KEY set in the environment
python -m src.scrapers.run_pipeline
```

This runs all three configured sources (`indigo_direct`, `airindia_direct`, `makemytrip`) across all five seeded routes and all three booking windows (T+1/T+7/T+30) — a full run takes several minutes given the polite per-request delay (`REQUEST_DELAY`, 30-35s per source). For a demo, that's too slow to run live end-to-end on stage; instead, either:

- Start the run a few minutes before the judge session so it's mid-flight, and show the terminal output / `scraper_runs` table update live, or
- Kick it off live and narrate what's happening (selector attempt → AI-parser fallback → validation → persistence) while it runs in the background, then check the DB for the row it just wrote.

**If it fails on stage — drop to Layer 2 immediately. Do not retry live, and do not stall trying to debug a scraper in front of judges.**

Known constraint: the three scrapers' CSS selectors are still placeholders (deferred in #17 — real selectors need live-DOM inspection this project hasn't done yet), so every live run currently goes through the Gemini AI-parser fallback rather than the selector-primary path. That's expected and fine for the demo — it's still a genuine live scrape producing genuine data, just via the fallback path rather than the primary one. Say so if asked; don't imply the selectors are working when they aren't.

## Layer 2 — Pre-warmed database (strong fallback)

If Layer 1 fails or isn't run, query the database for real historical data collected by the unattended collector (see "Keeping this honest" below) since #17 shipped. This is real data with real timestamps — show the judges the query running against the live DB, not a screenshot.

**Postgres:**

```bash
psql "$DATABASE_URL" -c "
SELECT sf.source, r.label AS route, sf.total_fare, sf.scrape_timestamp
FROM scraped_fares sf
JOIN routes r ON r.id = sf.route_id
WHERE sf.scrape_timestamp > NOW() - INTERVAL '30 days'
ORDER BY sf.scrape_timestamp DESC
LIMIT 50;
"

psql "$DATABASE_URL" -c "
SELECT source, status, started_at, finished_at, rows_scraped, rows_rejected
FROM scraper_runs
ORDER BY started_at DESC
LIMIT 20;
"
```

**SQLite (local dev):**

```bash
sqlite3 vegabytes.db "
SELECT sf.source, r.label AS route, sf.total_fare, sf.scrape_timestamp
FROM scraped_fares sf
JOIN routes r ON r.id = sf.route_id
WHERE sf.scrape_timestamp > datetime('now', '-30 days')
ORDER BY sf.scrape_timestamp DESC
LIMIT 50;
"

sqlite3 vegabytes.db "
SELECT source, status, started_at, finished_at, rows_scraped, rows_rejected
FROM scraper_runs
ORDER BY started_at DESC
LIMIT 20;
"
```

The second query (`scraper_runs`) is the forensic proof: it shows a history of unattended runs with real start/finish timestamps and row counts, which is much harder to fake convincingly than a table of prices.

**This layer is only as credible as how long the collector has actually been running before demo day.** A database with three rows from this morning proves nothing. This runbook cannot manufacture that history — it can only tell you to start the collector now (see below) so there's something real to show later.

## Layer 3 — Recorded proof (nuclear fallback)

If both Layer 1 and Layer 2 come up empty on stage (e.g. a corrupted demo environment), fall back to a recorded screen capture of a previous successful run, shown alongside the corresponding `scraper_runs` database entry as corroborating evidence.

**As of this runbook, no such recording exists yet.** This section defines the process the team should follow going forward, not an artifact already in hand:

1. **Weekly, once the unattended collector is running:** record a short (2-3 minute) screen capture of a full `python -m src.scrapers.run_pipeline` invocation — terminal output and the resulting `scraper_runs` row — with the system clock visible on screen.
2. **Naming convention:** `demo_assets/screencasts/YYYY-MM-DD_<source>.mp4` (create the `demo_assets/` directory when the first recording exists; keep recordings out of git — add `demo_assets/screencasts/` to `.gitignore` if this directory is created, matching how `data/raw/` is already excluded).
3. **What proves it's real:** the terminal's system clock, the `scraper_runs.id` visible in the run output, and a follow-up query against the live DB for that same run ID — a recording is only forensic proof if it's cross-checkable against the database afterward.
4. **Where to reference it in the demo:** if used, show the recording first, then immediately run the Layer 2 query filtered to that run's timestamp to prove the recording matches real persisted data.

We deliberately do **not** carry the "Layer 4 — Nuclear synthetic fallback" from the earlier draft in `docs/loopholes_260826.md` (a labeled synthetic dataset if everything else fails). Even honestly labeled, fabricated data on stage undercuts the same credibility this whole runbook exists to protect — see `docs/loopholes_260826.md`'s Loophole 4 section for the annotated rationale. If all three layers above fail, the right move is to say so plainly and pivot the demo to the index calculation methodology and dashboard, which don't depend on live data being available at that exact moment.

## Keeping this honest: start the collector now

Layers 2 and 3 are both dead without an actual unattended collector running before demo day (issue #17's task A5). If it isn't running yet:

```bash
# Example cron entry — every 4 hours, at least one source × 3-5 routes
0 */4 * * * cd /path/to/VegaBytes_25056 && \
  DATABASE_URL=... GEMINI_API_KEY=... \
  python -m src.scrapers.run_pipeline >> logs/pipeline.log 2>&1
```

Every hour this isn't running is permanent, unrecoverable lost history — you cannot retroactively scrape yesterday's prices. Start it today even if selectors are still on the AI-fallback path.

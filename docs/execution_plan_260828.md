# VegaBytes — Execution Plan & Codebase Audit

**Date:** 28 August 2026 · **Internal deadline:** 4 September 2026 (7 days) · **Status:** action required

A full audit of the codebase, docs, branches, issues and open PRs, and the prioritised plan that
follows from it. This supersedes the sequencing implied by `loopholes_260826.md` — that document
identified the right *risks*, but the code written since has not closed them.

---

## 1. The finding that reorders everything

**The pipeline cannot currently produce a single fare record.** Not "is incomplete" — cannot
produce one. A scrape dies five times, and each failure hides the next:

| # | Failure | Evidence |
|---|---------|----------|
| 1 | All three scrapers use placeholder CSS classes that match no website, so extraction always returns `[]` | `makemytrip.py:110` `.listingCard-placeholder`, `airindia_direct.py:110` `.flight-card-placeholder`, `indigo_direct.py:120` `.fare-card  # UPDATE THIS` |
| 2 | The AI fallback triggers on `if not records:` — so it fires on **every** request for every source, inverting the documented "fallback only" design | `indigo_direct.py:85`, design intent at `ai_dom_parser.py:5` |
| 3 | The fallback calls `"gemini-1.5-flash"` — a **retired model ID**. Current clients get a 404-class error | `ai_dom_parser.py:58` |
| 4 | That error is swallowed by `except (json.JSONDecodeError, Exception)` and returns `[]`. Zero records, zero alerts | `ai_dom_parser.py:95` |
| 5 | Nothing persists. **There is no database code anywhere in the repo** | `psycopg2`/`sqlalchemy`/`alembic` declared `pyproject.toml:12-14`, never imported; records `print()`ed at `test_scraper.py:57` and discarded |

### Consequences that compound

- **`python -m src.scrapers.run_pipeline` does not exist.** It is printed in `README.md:108` and run
  by `scraper_cron.yml.disabled:30`. `src.index.compute_daily` doesn't exist either. This is the
  first command a technical judge will type.
- **Tax separation — an explicit PS deliverable — is at zero.** Every scraper hardcodes
  `base_fare=None, fuel_surcharge=None, udf=None, psf=None, gst=None` (`indigo_direct.py:134-138`
  and the two copies). The validator's `base_fare > total_fare` guard (`validator.py:66-70`)
  therefore can never fire, and the index would run on gross fares — contradicting `laspeyres.py:13`.
- **There is no automated gate at all.** Both CI workflows are `.disabled`, and CodeRabbit runs
  `request_changes_workflow: false` (`.coderabbit.yaml:14`). That is precisely how placeholder
  selectors reached `main` and how Issue #13 was closed on a scraper that cannot work.
- **The two halves of the project are disconnected.** The dashboard has no `fetch`, no HTTP client,
  and no `rewrites` in `next.config.ts`. It has never talked to the API.
- **Zero scraper tests exist.** `test_scraper.py` is a `__main__` driver, not pytest-collectable,
  and sits outside `testpaths = ["tests"]` (`pyproject.toml:52`).

### Guiding principle

> **One honest thread beats five stubs.** One route, one source, real fares — persisted, indexed,
> served by the API, rendered on the dashboard — outscores three scrapers × six routes of
> placeholders. Build the thread, then widen it.

---

## 2. Track A — Tonight (~3h, Shardul). Blocks everything else

Time-series depth is **the only thing that cannot be bought back later.** You cannot retroactively
scrape yesterday's prices. Every hour of delay is permanent loss — and this work deliberately does
**not** wait on Mukta's Postgres.

**A1 · Persist to SQLite now, Postgres later.** Add `src/db.py` with a SQLAlchemy engine reading
`DATABASE_URL`, defaulting to `sqlite:///vegabytes.db`. Zero infra dependency; swaps to Postgres by
changing one env var.

**A2 · Write the missing `src/scrapers/run_pipeline.py`.** Loop sources × routes × booking windows
(T+1/T+7/T+30) → `PriceValidator.validate_batch` (already written, `validator.py:74`) → write valid
rows to `scraped_fares`, rejects to `data_quality_log`, one row per run to `scraper_runs`. Reuse
`ScraperFactory.get()` (`base.py:95`); note `src/scrapers/__init__.py` re-exports nothing, so the
runner must import each scraper module explicitly to populate the registry.

**A3 · Fix the model ID and the silent failure.** `ai_dom_parser.py:58` → `gemini-2.5-flash` (verify
against the live API first), env-overridable via `GEMINI_MODEL`. Split the catch-all at `:95` so
auth/transport errors are logged loudly and distinguishably from parse failures. A silent `[]` is
the single most dangerous line in this codebase.

**A4 · Archive raw HTML on every scrape — the highest-leverage change in this plan.** Write each
page to `data/raw/<source>/<route>/<timestamp>.html.gz` and store the path on the fare row. One
change, five problems solved:

- Develop and test selectors offline against real HTML — no re-scraping, no ban risk.
- Gives the scrapers their first regression tests.
- Makes the AI-recovery demo deterministic and replayable from fixtures, not live-site luck.
- Supplies the forensic collection proof Issue #4 asks for.
- **Enables retroactive reprocessing.** When tax separation lands on Day 4, re-derive
  `base_fare`/`udf`/`gst` for every page captured since tonight. Starting late stops costing history.

**A5 · Start the collector.** One source, 3–5 routes, `cron`/`systemd`/`nohup` on any always-on
machine. Partial success is acceptable; rows flowing tonight matters more than rows being perfect.

> Because selectors are non-functional, the AI parser is realistically the **fastest path to real
> rows tonight**. Run AI-first deliberately and temporarily to bootstrap data + HTML fixtures, then
> harden selectors from those fixtures on Day 2 and restore selector-first ordering.

---

## 3. Track B — The 7-day sprint, by owner

### Shardul — scraping (Issues #4, #7-followup, #17, #19)
- ✅ Issue #4 (demo-day resilience): see `docs/demo_day_runbook.md` for the layered live →
  pre-warmed-database → recorded-proof strategy that replaced the Kaggle fallback.
- Day 2: derive **real IndiGo selectors** from the Track-A archive; delete every `-placeholder`
  class; restore selector-primary / AI-fallback ordering.
- Change the fallback trigger from `if not records:` to a distinct `SelectorExtractionError` plus a
  plausibility check — today a genuinely empty result (no flights) and selector breakage are
  indistinguishable, and each burns a Gemini call.
- Correctness bugs found in audit: `cabin_class` is accepted then ignored with `"economy"` hardcoded
  into the record (`indigo_direct.py:132`) — business-class requests are silently mislabelled;
  `airline="MakeMyTrip OTA"` (`makemytrip.py:119`) is not an airline and corrupts per-carrier
  aggregation; `browser.close()` is not in `try/finally`, leaking a Chromium process per failure
  × 3 tenacity retries; `.lstrip("```json")` (`ai_dom_parser.py:92`) strips a *character set*, not a
  prefix — use `removeprefix`.
- Deduplicate the three copy-pasted scrapers into shared `BaseScraper` helpers.

### Rahul — tax separation (Issue #5) — the PS deliverable currently at zero
- Commit `data/aai_udf_psf.csv` (AAI-published airport fees) and GST rates (5% economy / 12% business).
- Target the **fare-breakdown / booking-summary page**, not the search-results total — that is where
  Base + Fuel + UDF + PSF + GST appear as separate line items.
- Unit test: given a known total and route, ETL isolates the correct base fare.
- Reprocess the Track-A HTML archive to backfill every row collected since Day 0.
- Housekeeping: `refactor-airindia-scraper` is orphaned — one commit adding only
  `docs/research_issues.md`, never PR'd. Land it or delete it.

### Ankita — index + the differentiator (Issue #2)
- `routes.dgca_weight` is seeded `0.0` for all five routes (`db/schema.sql:79-85`). Commit
  `data/dgca_route_weights.csv` **with documented provenance** (release, quarter, route mapping) —
  CodeRabbit already flagged unprovenanced weights on PR #11.
- Write `docs/apix_formula_spec.md`: weight derivation, base period, carry-forward imputation, 3σ
  outlier clipping.
- **Build the real back-test — the highest-scoring item available.** MoSPI exposes CPI via API with
  Item-level granularity, base years 2012 and 2024 (verified against the live API). Pull the official
  airfare/transport series and overlay it against APIx. Publish a comparability contract (base year,
  booking window, fare scope, route universe, missing-data policy) so it is a defensible back-test
  rather than a vibes-based chart. *No other team will do this*, and it converts "is your index
  sound?" from an interrogation into the strongest slide in the deck.

### Mufeed — API + validation (Issue #6)
- Wire all four endpoints to the DB. Today `/api/v1/index` raises `501` (`api/main.py:71`) and the
  other three return hardcoded empties (`:86`, `:99`, `:105`).
- Implement `/api/v1/pipeline/status` from `scraper_runs` — the dashboard health panel depends on it.
- Add dedup (same flight + departure_date + window + source within 30 min) and `data_quality_log` writes.
- Restrict `allow_origins=["*"]` (`api/main.py:39`) to the dashboard origin.
- Add API tests — there are none.

### Mukta — infra (Issues #3, #8)
- Postgres (Supabase/Neon) + apply `db/schema.sql`; team flips `DATABASE_URL` off SQLite.
- Migrate the Track-A collector to GitHub Actions cron (works only after Track A lands).
- Wire `TelegramAlerter` + `FailureTracker` (`monitoring/alerter.py` — written, never called) into
  `run_pipeline`. Test by simulating three consecutive failures.
- **Deprioritise the proxy pool.** IndiGo direct is the demo path and needs no proxy. Do not let the
  MakeMyTrip/Akamai block hold up the sprint.
- `docs/infrastructure.md`.

### Shubham — dashboard + pitch (Issues #9, #18)
- Port PR #14's Recharts trend, `FaresExplorer` and `services/api.js` into the Next.js app on `main`;
  close #14 with credit. **Decision: Next.js survives, Vite app is retired.**
- Fix #14's outstanding bot findings first — dead route search/filter controls
  (`FaresExplorer.jsx:33-57`), unbounded pagination, KPI/chart disagreement from a hardcoded
  `apix_value: 142.56`.
- Point the service layer at the real FastAPI.
- Replace `title: "Create Next App"` (`layout.tsx:16-17`) and delete the boilerplate home page.
- Rebuild `/compliance` on real `scraper_runs` data — see §4.
- `globals.css` has no `@tailwind` / `@import "tailwindcss"` directives, so Tailwind classes used
  across the app are almost certainly not compiling.

---

## 4. Track C — Defuse the credibility landmines (~2h)

Domain judges read the docs, then the code. The docs currently write cheques the code cannot cash,
and a single catch collapses trust in everything else.

| Claim | Where | Reality |
|---|---|---|
| "142 Residential IPs", "100% evasions", "1.25 req/min" | `compliance/page.tsx:95-107` | Hardcoded. The "residential IPs" shown are RFC1918 **private** addresses (`192.168.1.104`, `10.0.0.45`). Fabricated compliance evidence on a *legal-defensibility* tab is the worst possible thing to be caught with. |
| "parameterised queries via SQLAlchemy ORM" | `SECURITY.md` | No database code exists. |
| "SQLAlchemy ORM", "Alembic tracks migrations" | `architecture.md:34-35` | Neither is imported anywhere. |
| `python -m src.scrapers.run_pipeline` | `README.md:108` | Module does not exist — crashes on the first command a judge types. |
| Proxy rotation, tax isolation, "<2 req/min enforced" | PR #11 pitch deck | All three flagged unsupported by CodeRabbit. No rotation; taxes all `None`; the delay is a fixed per-job `time.sleep`, not a shared concurrency-aware limiter. |
| "Zero PII collected" | README, pitch, compliance tab | `AIdomParser` ships **raw page HTML unsanitised to Google's API** — a third-party data transfer. Strip/limit before sending and reword to "no PII is intentionally collected or stored". |

**Rule to adopt:** anything shown on the compliance tab must be a database query, never a literal. An
honest *"3 sources monitored, 41 requests today, 1.4 req/min observed"* beats a fabricated 142.

---

## 5. Track D — Restore the gates (~1h, Shardul)

An unmeetable gate is why CI got disabled; restore a *meetable* one.

- Rename `ci.yml.disabled` → `ci.yml`, but first: drop `--cov-fail-under=70` to ~30 and ratchet up
  (real coverage is ~20–25%, so the gate fails deterministically today); relax `mypy --strict`
  (`pyproject.toml:57`); add a Postgres service container (`DATABASE_URL` is already set in the job);
  run `black` once repo-wide so `--check` can pass.
- Fix `[tool.ruff] select` → `[tool.ruff.lint] select` (`pyproject.toml:47`). On the deprecated
  top-level form the `B` ruleset — which would have caught every bare `except` — may not be applying.
- Pin `playwright-stealth>=2.0.0` (`pyproject.toml:8` allows `>=1.0.6`, but the code uses the 2.x
  `Stealth()` API; a fresh resolve could `ImportError` on a teammate's machine).
- Set `request_changes_workflow: true` in `.coderabbit.yaml`.
- Add the dashboard to CI (`npm run build` + lint) — currently unchecked by anything.
- Branch hygiene: delete merged `feature/legal-defensibility`, `feat/issue-13-scrapers`,
  `fix/issue-7-ai-parser`. Reopen Issue #13 or file a follow-up — the Air India scraper it closed
  cannot work.

---

## 6. Track E — After 4 September: playing for the national finale

The internal round is the near gate; the finale is months out. That changes what compounds.

1. **Data depth is the moat.** A collector started tonight yields months of continuous, timestamped,
   un-fakeable Indian airfare time-series by the finale. A team starting in November cannot
   replicate it. This alone justifies Track A.
2. **Publish the methodology** — `apix_formula_spec.md` + the MoSPI back-test as a short paper.
   National-level judges respond to statistical rigour over UI polish.
3. **Full provenance** — every APIx value drillable to the raw scrapes and archived HTML behind it.
   Economists care about revision policy and auditability more than heatmaps.
4. **Cross-source validation** as a real feature (Loophole 6): same flight across IndiGo-direct and
   an OTA, divergence flagged and surfaced.
5. **Prove the scalability claim** rather than asserting it — a second vertical (rail or hotel)
   plugged in via `ScraperFactory` with zero changes to index/API/dashboard *demonstrates* the
   factory-pattern argument the pitch currently only states.

---

## 7. Verification

```bash
# A: the README's own command runs and writes rows
python -m src.scrapers.run_pipeline --source indigo_direct --route DEL-BOM --window 7
sqlite3 vegabytes.db "SELECT COUNT(*), MIN(scrape_timestamp), MAX(scrape_timestamp) FROM scraped_fares;"
# expect a growing count and timestamps spanning days

# tax separation actually populated (returns 0 today)
sqlite3 vegabytes.db "SELECT COUNT(*) FROM scraped_fares WHERE base_fare IS NOT NULL;"

# B: API serves real data, not 501/empty
uvicorn src.api.main:app --port 8000 &
curl -s localhost:8000/api/v1/index | jq           # real apix_value, not 501
curl -s localhost:8000/api/v1/pipeline/status | jq # freshness "fresh", not "critical"

# C/D: gates green
ruff check src/ tests/ && black --check src/ tests/ && pytest --cov=src
cd dashboard && npm run build

# the differentiator demos deterministically
pytest tests/test_ai_fallback.py  # selector breaks against archived fixture, AI recovers price
```

**Then the end-to-end rehearsal**, which is what the round actually scores: start the API, load the
dashboard, confirm the APIx figure on screen traces to real rows in `scraped_fares`, and confirm the
compliance tab's numbers come from `scraper_runs` queries rather than literals. Run the
selector-break → AI-recovery demo from the archived fixture, not the live site.

---

## The one-line version

**Stop building breadth and make one route real, tonight — then spend the remaining six days making
the docs true and the back-test official.**

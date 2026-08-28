# Implementation Plan — Issues Assigned to Shardul (#17, #19, #4)

## Context

A 28-Aug codebase audit (`docs/execution_plan_260828.md`, landed via PR #20) found that VegaBytes' scraping pipeline is non-functional end to end, its CI is fully disabled, and several docs/dashboard claims describe features that don't exist. That audit was filed as issues #2–9, #13, #17–19. Of those, **three are assigned to Shardul (shard-c6)**:

- **#17 [BLOCKER]** — the pipeline cannot produce a single fare record: placeholder CSS selectors, a retired Gemini model ID, a silent catch-all exception, and zero persistence code anywhere. This blocks #2, #4, #5, #6, #8.
- **#19 [HIGH]** — both CI workflows are `.disabled` and CodeRabbit can't block merges, which is how broken/placeholder code reached `main`; several docs also claim capabilities (SQLAlchemy ORM, Alembic, "zero PII") that don't exist in the code.
- **#4 [HIGH]** — the current demo-day fallback plan is "use a Kaggle dataset," which is dishonest and would be spotted instantly by a judge; needs replacing with a 3-layer strategy built on real scraped data.

All three were independently verified against the current code (line numbers below are confirmed, not just asserted by the issues). Goal of this plan: get real data flowing (#17) first since #19 and #4 both reference facts that only become true once it lands, then restore CI/fix docs (#19) and write the demo runbook (#4) in parallel. Work stays anti-fabrication throughout — no invented data, videos, or metrics — consistent with the audit's own guiding principle and issue #18's parallel cleanup of the dashboard.

Each issue closes via its own PR, in this order: **PR 1 (#17) → PR 2 (#19) + PR 3 (#4)**.

**Status:** PR 1 (#17) is implemented on branch `claude/assigned-issues-plan-f9t81h` — see the "Implementation notes" section at the bottom of this doc for what landed and how it was verified. PR 2 (#19) and PR 3 (#4) are planned but not yet started.

---

## PR 1 — Issue #17: make the pipeline produce real rows

**Confirmed current state:**
- `src/scrapers/{makemytrip,airindia_direct,indigo_direct}.py` all use placeholder CSS selectors (e.g. `indigo_direct.py:120` `.fare-card  # UPDATE THIS`) that match nothing, so every scrape falls through to the AI fallback.
- `src/scrapers/ai_dom_parser.py:58` — `model_name: str = "gemini-1.5-flash"` (retired). Line 92 has a real bug: `response_text.strip().lstrip("```json").rstrip("```")` — `lstrip`/`rstrip` strip *character sets*, not prefixes, so this doesn't do what it looks like it does. Line 95's `except (json.JSONDecodeError, Exception)` swallows literally everything (auth, quota, network, parse) into one silent `return []`.
- `src/scrapers/base.py:95` `ScraperFactory.get()` works fine, but `src/scrapers/__init__.py` is just a docstring — scrapers only register when their module is explicitly imported.
- No `src/db.py`, no `src/scrapers/run_pipeline.py` anywhere, despite `README.md:108` and `scraper_cron.yml.disabled:30` referencing the latter. `psycopg2-binary`/`sqlalchemy`/`alembic` are declared in `pyproject.toml` but never imported anywhere.
- `db/schema.sql` already defines `routes`, `scraped_fares`, `data_quality_log`, `index_values`, `scraper_runs` (with `source`, `source_url`, `scrape_timestamp` columns) — no raw-HTML column yet.
- `src/etl/validator.py`'s `PriceValidator.validate_batch()` (line 74) is fully implemented and unused by anything.
- `test_scraper.py` scrapes and only `print()`s — nothing persists.
- No `data/` directory or raw-HTML-archiving code exists.

**Changes:**

1. **`src/db.py` (new)** — SQLAlchemy **Core** (not a full ORM class hierarchy — keep it minimal). `DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///vegabytes.db")`, `engine = create_engine(DATABASE_URL, future=True)`. Declare the 5 tables as `sqlalchemy.Table` objects with dialect-portable types (Python-side `uuid4()` default instead of `uuid_generate_v4()`, a plain computed `label` populated in code instead of Postgres `GENERATED ALWAYS AS ... STORED`) so `metadata.create_all(engine)` works on a fresh SQLite file with zero setup — `db/schema.sql` stays canonical for Postgres. Helper functions: `get_route_id`, `insert_scraped_fares`, `insert_rejections`, `start_scraper_run`/`finish_scraper_run`.

2. **`src/scrapers/run_pipeline.py` (new)** — explicitly `import src.scrapers.{indigo_direct,airindia_direct,makemytrip}` at top to populate the `ScraperFactory` registry (required, not optional). Loop sources × the 5 seeded routes × booking windows `[1, 7, 30]` → `ScraperFactory.get(source).scrape_route(...)` → `PriceValidator().validate_batch(records)` → valid rows to `scraped_fares`, rejects to `data_quality_log`, one `scraper_runs` row per source per invocation (wrap each source's loop in try/except so one crash doesn't kill the others' accounting). Add `if __name__ == "__main__":` so `python -m src.scrapers.run_pipeline` works as README/cron already expect. Reuse the `structlog` setup pattern from `test_scraper.py`.

3. **Fix `src/scrapers/ai_dom_parser.py`:**
   - `model_name: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")` (env-overridable, verify the model ID is live before merging).
   - Split line 85–97 into two try blocks: one around the Gemini API call (`except Exception as e: log.error("gemini_api_call_failed", ...)`) and one around JSON parsing (`except json.JSONDecodeError as e: log.error("gemini_response_not_json", ...)`) — auth/network/quota failures now log loudly and distinctly from parse failures, instead of one silent catch-all.
   - Fix the prefix-strip bug: `.removeprefix("```json").removesuffix("```").strip()` instead of `.lstrip`/`.rstrip`.

4. **Raw HTML archive (issue's A4, the highest-leverage item):** add `raw_html_path TEXT` column to `scraped_fares` in `db/schema.sql` (and the matching `src/db.py` table def). Add a shared `archive_html(source, route, html) -> str` helper in `src/scrapers/base.py` that gzips the page HTML to `data/raw/<source>/<route>/<timestamp>.html.gz` and returns the path. Add `raw_html_path: Optional[str] = None` to the `FareRecord` dataclass. Each of the 3 scrapers calls `archive_html()` at the point it already builds `html_fragment` for the AI parser, and stamps the path onto every record it emits. `data/raw/` was already in `.gitignore`.

5. **Selector hardening — explicitly deferred.** No live browser access to inspect real DOM in this environment, and per the issue's own guidance the AI-parser path is the pragmatic route to real rows tonight. Placeholder selectors are marked with a `# DEFERRED — see issue #17 follow-up` comment rather than guessing at selectors (a guessed selector that matches nothing is no better than today; one that matches the wrong element is worse — silently poisoned data).

6. **A5 (start the collector)** is an operational step, not a diff — run `run_pipeline.py` unattended via cron/nohup for at least 1 source × 3–5 routes on an always-on machine.

**Files touched:** new `src/db.py`, `src/scrapers/run_pipeline.py`; edited `src/scrapers/ai_dom_parser.py`, `src/scrapers/base.py`, `src/scrapers/{makemytrip,airindia_direct,indigo_direct}.py`, `db/schema.sql`.

**Verification:**
- `python -m src.scrapers.run_pipeline` runs to completion against default SQLite, no `ValueError` from an unregistered scraper.
- `scraped_fares` gains rows (`sqlite3 vegabytes.db "select count(*), source from scraped_fares group by source;"`), `scraper_runs` gets one row per source with `status`/`finished_at` set.
- `data/raw/.../*.html.gz` files exist, are valid gzip, and every `raw_html_path` in the DB points to a real file.
- Break `GEMINI_API_KEY` and confirm `gemini_api_call_failed` appears (not a silent empty return); confirm a malformed response instead logs `gemini_response_not_json`.
- Existing `tests/test_validator.py`, `tests/test_laspeyres.py` still pass unmodified.

---

## PR 2 — Issue #19: restore CI gates, fix config bugs, fix dishonest docs

**Confirmed current state:** only `.github/workflows/ci.yml.disabled` / `scraper_cron.yml.disabled` exist. `ci.yml.disabled:40` has `--cov-fail-under=70` (unmeetable — real coverage ~20-25%); lines 41-42 set a `DATABASE_URL` env var with no Postgres service container behind it. `.coderabbit.yaml:14` has `request_changes_workflow: false`. `pyproject.toml:45-48` uses the deprecated top-level `[tool.ruff] select=...` form; `:56-57` has `mypy strict = true`; `:8` pins `playwright-stealth>=1.0.6` while the code (all 3 scrapers) uses the 2.x `Stealth().apply_stealth_sync()` API and `uv.lock` happens to resolve 2.0.3. `src/api/main.py:79` has misaligned `=` spacing that fails `black --check`. `dashboard/` has its own build/lint but is checked by nothing. `SECURITY.md`/`docs/architecture.md` claim a SQLAlchemy ORM + Alembic migrations that don't exist; "zero PII collected" language appears in README/SECURITY.md/docs/dashboard compliance tab while `ai_dom_parser.py` sends raw unsanitized HTML to Gemini. Three merged branches (`feature/legal-defensibility`, `feat/issue-13-scrapers`, `fix/issue-7-ai-parser`) and one orphaned branch (`refactor-airindia-scraper`, one commit, never PR'd) are confirmed still present via `list_branches`.

**Changes:**

1. **CI workflows:** `git mv ci.yml.disabled ci.yml`. Edit: coverage threshold `70` → `30`; add a `services: postgres:` block (image `postgres:16`, matching the `test:test@localhost:5432/test` creds already in the env var) so `DATABASE_URL` resolves to something real; add a dashboard job/steps (`working-directory: dashboard`, `npm ci`, `npm run build`, `npm run lint`). `git mv scraper_cron.yml.disabled scraper_cron.yml` (safe now that PR 1 makes `run_pipeline` real) — but its `compute_daily` step (line 39) still references a module that doesn't exist and is out of scope here (owned by Ankita/#2 index work); guard it with `continue-on-error: true` plus a `# TODO: src/index/compute_daily.py not yet implemented` comment rather than faking the module.

2. **`.coderabbit.yaml`:** `request_changes_workflow: false` → `true`.

3. **`pyproject.toml`:** move `select`/`ignore` under `[tool.ruff.lint]`; drop `strict = true` from `[tool.mypy]`; bump `playwright-stealth` to `>=2.0.0`; regenerate `uv.lock` via `uv lock`.

4. **Formatting:** run `black src/ tests/` repo-wide once (fixes `src/api/main.py:79` and anything else); skim the diff to confirm no semantic changes.

5. **Docs honesty fixes:**
   - `SECURITY.md`: "parameterised queries via SQLAlchemy ORM" → "via SQLAlchemy Core" (true once PR 1 lands — no declarative model classes exist, so don't claim "ORM").
   - `docs/architecture.md:34-35`: rewrite the ORM/Alembic claims to describe what's actually there — SQLAlchemy Core in `src/db.py`, hand-maintained `db/schema.sql`, no migration tool.
   - Reword "zero PII collected" everywhere it appears (`README.md`, `SECURITY.md`, `docs/loopholes_260826.md`, `docs/project_idea_elaboration.md`, `docs/execution_plan_260828.md`) to **"no PII is intentionally collected or stored — scrapers extract only public price, route, and timestamp data."**
   - Add a small `_strip_noise(html) -> str` helper in `ai_dom_parser.py` (use the already-a-dependency BeautifulSoup to drop `<script>`/`<style>`/`<input>`/`<form>` tags) called before the existing 8000-char truncation, so the reworded claim has real backing rather than being purely aspirational.
   - `dashboard/src/app/compliance/page.tsx:106-107`: reword the hardcoded `"PII Collected: 0 Bytes"` tile — a fake-precise stat implying instrumentation is exactly the anti-pattern issue #18 is separately cleaning up; replace with the same honest policy sentence, not a fabricated number.
   - Verify every command in `README.md` actually runs (the `run_pipeline` one now does, post-PR-1).

6. **Repo hygiene:** re-verify against the live GitHub remote (already confirmed via `list_branches` in this session) that `feature/legal-defensibility`, `feat/issue-13-scrapers`, `fix/issue-7-ai-parser` are merged, then delete them (`git push origin --delete <branch>`). For `refactor-airindia-scraper`: its one commit only adds `docs/research_issues.md` — check if that content is still useful; if not, delete the branch, if so land it in a tiny separate PR rather than folding into #19. File a follow-up issue noting the Air India scraper (#13) is still a placeholder rather than silently reopening #13.

**Files touched:** renamed `.github/workflows/{ci,scraper_cron}.yml`; edited `.coderabbit.yaml`, `pyproject.toml`, `uv.lock`, `SECURITY.md`, `docs/architecture.md`, `README.md`, `docs/loopholes_260826.md`, `docs/project_idea_elaboration.md`, `docs/execution_plan_260828.md`, `src/scrapers/ai_dom_parser.py`, `dashboard/src/app/compliance/page.tsx`, plus black's mechanical formatting pass.

**Verification:**
- Push and confirm `ci.yml` goes green on GitHub Actions: ruff, black --check, mypy, pytest (`--cov-fail-under=30`), dashboard build+lint, Postgres service healthy.
- `grep -ri "zero pii" -r . --include=*.md --include=*.tsx` returns nothing.
- Re-read `SECURITY.md`/`docs/architecture.md` end-to-end for any other now-false claim near the edited lines.
- README badges resolve (no 404) once workflows are renamed.

---

## PR 3 — Issue #4: layered demo-day resilience strategy (depends on PR 1 for Layer 1 to be real)

**Confirmed current state:** `docs/project_idea_elaboration.md:135` has the Kaggle fallback line to remove. `docs/loopholes_260826.md:70-84` already sketches a near-identical 4-layer version (including a "nuclear synthetic fallback" layer) with a to-do at line 213 to replace the Kaggle language — issue #4 asks for only 3 layers, deliberately dropping the synthetic-data layer since it conflicts with the project's anti-fabrication stance (same principle driving #18/#19). `db/schema.sql` already has the `source`/`source_url`/`scrape_timestamp` columns and `scraper_runs` table needed to prove authenticity — no schema work needed here. No videos/recording scripts exist anywhere yet.

**Changes:**

1. **New `docs/demo_day_runbook.md`** with three layers:
   - **Layer 1 (live):** exact command to run a live IndiGo-direct scrape during the demo (post-PR-1, via `run_pipeline.py`, scoped to one source/route if a small `--source`/`--route`/`--window` CLI flag is worth adding — otherwise document the existing full-run invocation). Explicit instruction: if it fails on stage, drop to Layer 2 immediately, don't retry live.
   - **Layer 2 (pre-warmed DB):** exact SQL against `scraped_fares`/`scraper_runs` to show real multi-week history with timestamps as forensic proof, runnable via `psql`/`sqlite3` depending on backend. Note explicitly that this layer's credibility is only as good as how long the unattended collector (PR 1's A5) has actually been running before demo day — this plan can't pre-populate that honestly.
   - **Layer 3 (recorded proof):** a weekly *process* checklist (what to record, naming convention, where to store outside git) — stated explicitly as "no video exists yet; this defines how the team produces one going forward," not a fabricated artifact.
   - Cross-reference `docs/execution_plan_260828.md`'s Track A section and `docs/loopholes_260826.md`'s Loophole 4.

2. **Edit `docs/project_idea_elaboration.md:135`** — replace the Kaggle sentence with a pointer to the new runbook and an explicit "no synthetic or third-party data is used anywhere" statement.

3. **Edit `docs/loopholes_260826.md`** — mark the line-213 to-do done, point at the runbook, and annotate (don't silently delete) the dropped "Layer 4 / nuclear fallback" with a one-line rationale for why it was cut.

4. **Edit `docs/execution_plan_260828.md`** — one cross-reference line near the existing Shardul section pointing at the new runbook (coordinate with PR 2 so both don't collide on this file — PR 2 shouldn't touch this section).

**Files touched:** new `docs/demo_day_runbook.md`; edited `docs/project_idea_elaboration.md`, `docs/loopholes_260826.md`, `docs/execution_plan_260828.md`; optionally a small CLI-scoping addition to `src/scrapers/run_pipeline.py`.

**Verification:**
- Manually run the exact Layer 1 and Layer 2 commands from the runbook end-to-end post-PR-1 and confirm they produce the described output against real data.
- `grep -ri kaggle -r .` — confirm no remaining reference implies it's still in the live plan (mentions in `loopholes_260826.md`'s decision log explaining why it was rejected are fine).
- Have someone follow the runbook cold to confirm the commands are copy-pasteable and correct.

---

## Sequencing notes
- PR 1 should merge (or at least be rebased in) before PR 2's CI can meaningfully exercise the new code, and before PR 3's runbook commands can be verified against real behavior.
- PR 2 and PR 3 both touch `docs/execution_plan_260828.md` — keep each PR's edit to a different section to avoid a conflict.
- None of the three PRs touch `db/schema.sql`'s seed weights, `src/index/laspeyres.py`, or `src/api/main.py` beyond PR 2's mechanical black-formatting fix — those stay owned by Ankita/Mufeed per the other open issues.

---

## Implementation notes (PR 1 / Issue #17 — done)

Landed on `claude/assigned-issues-plan-f9t81h`:

- `src/db.py` — SQLAlchemy Core engine + `routes`/`scraped_fares`/`data_quality_log`/`scraper_runs` tables, `ensure_schema()` (creates tables and seeds the 5 routes on SQLite), and helpers (`get_route_id`, `insert_scraped_fares`, `insert_rejections`, `start_scraper_run`/`finish_scraper_run`).
- `src/scrapers/run_pipeline.py` — orchestrates sources × routes × booking windows `[1, 7, 30]`, validates via `PriceValidator`, persists valid/rejected rows, and records one `scraper_runs` row per source per invocation. A crash in one source's loop is caught and recorded as `status="failed"` without stopping the other sources (verified with a mocked run where `airindia_direct` raised and `indigo_direct`/`makemytrip` still completed and persisted).
- `src/scrapers/ai_dom_parser.py` — model ID now `os.getenv("GEMINI_MODEL", "gemini-2.5-flash")`; the API call and JSON-parse steps are now in separate `try` blocks logging `gemini_api_call_failed` vs `gemini_response_not_json` respectively; fixed the `.lstrip("```json").rstrip("```")` bug (stripped a character set, not a prefix) to `.removeprefix(...).removesuffix(...)`.
- `src/scrapers/base.py` — added `FareRecord.raw_html_path` and an `archive_html(source, route, html)` helper that gzips page HTML to `data/raw/<source>/<route>/<timestamp>.html.gz`.
- `src/scrapers/{indigo_direct,airindia_direct,makemytrip}.py` — each now archives the full page HTML right after page load and stamps the resulting path onto every record it returns (selector-path or AI-fallback path). Placeholder selectors are marked `# DEFERRED — see issue #17 follow-up` rather than guessed at, since this session has no live-browser access to inspect real DOM.
- `db/schema.sql` — added `scraped_fares.raw_html_path TEXT`.

**Verified in this session** (no live network/browser access, so verification is at the unit/orchestration level, not against real airline sites):
- `db.py` round-trips all 4 tables against a scratch SQLite file, including `raw_html_path`.
- `ai_dom_parser.py`: mocked an API failure (logs `gemini_api_call_failed`), a malformed response (logs `gemini_response_not_json`), and a well-formed fenced-JSON response (parses correctly, proving the `removeprefix`/`removesuffix` fix works).
- `archive_html()` writes real gzip files with the expected path shape.
- `run_pipeline.py` end-to-end with scrapers' `scrape_route` mocked (to avoid hitting real airline sites without a live demo context): all 3 sources register via `ScraperFactory`, one source crashing doesn't block the others, `scraper_runs`/`scraped_fares` end up correctly populated.
- `black`/`ruff` clean on the new files; existing `tests/` pass except a pre-existing, unrelated `test_laspeyres.py` failure confirmed present on `main` before this change too.

**Not done (explicitly out of scope for #17, or operational rather than code):**
- Real CSS selectors for the three scrapers — deferred, needs live-DOM inspection.
- A5 (running the collector unattended on a real machine) — operational, to be done outside this session.
- `python -m src.index.compute_daily` (referenced by `scraper_cron.yml.disabled`) still doesn't exist — out of scope (Ankita/#2), to be handled in PR 2's CI-workflow guard.

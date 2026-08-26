# Contributing to VegaBytes — SIH PS 26056

## Branch Protection Rules

- **`main` is protected.** Direct pushes are forbidden.
- All changes must go through a **Pull Request (PR)** with at least **1 reviewer approval**.
- PRs must be linked to a **GitHub Issue** (use `Closes #<issue-number>` in the PR description).
- All CI checks must pass before merging.

## Branch Naming Convention

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feat/<your-name>/<short-description>` | `feat/shardul/stealth-scraper` |
| Fix | `fix/<your-name>/<short-description>` | `fix/mukta/proxy-rotation-bug` |
| Data/Research | `data/<your-name>/<short-description>` | `data/ankita/laspeyres-formula` |
| Docs | `docs/<your-name>/<short-description>` | `docs/shubham/pitch-deck-outline` |

## Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(scope): <short summary>

Examples:
feat(scraper): add stealth playwright config for IndiGo
fix(etl): handle null base fare when flight is sold out
data(index): implement Modified Laspeyres formula with DGCA weights
docs(pitch): add legal defensibility section to Q&A
```

**Types:** `feat`, `fix`, `data`, `docs`, `test`, `chore`, `refactor`

## Pull Request Rules

1. **Title:** Must follow the commit format above.
2. **Description:** Must include:
   - What was done
   - How to test it
   - `Closes #<issue-number>`
3. **Size:** Keep PRs focused. One issue = one PR. Do not bundle unrelated changes.
4. **Review:** Tag the team lead of the relevant tier for review.

## Issue Assignment Rules

- **Do not self-assign issues** not in your tier without discussion.
- If blocked, comment on the issue within **24 hours** — do not go silent.
- Issues must be closed via a PR, not manually.

## Code Standards

- **Python:** Follow PEP 8. Use `black` for formatting and `ruff` for linting.
- **SQL:** Use uppercase for SQL keywords. Table/column names in `snake_case`.
- **All secrets** (proxy credentials, DB URLs, API keys) go in `.env` files — **never commit secrets to the repo.**
- Add your module to the `README.md` once it is functional.

## Data & Scraping Ethics

- All scrapers must respect `robots.txt` crawl delays.
- Request rate must stay below **2 requests/minute per IP**.
- No PII is to be stored. Only price data with timestamps.
- Log every scraping session with: start time, rows collected, errors, proxy used.

## Escalation

If you are blocked for more than **12 hours**, ping `@shard-c6` on the team channel immediately. We cannot afford delays with the September 4 deadline.

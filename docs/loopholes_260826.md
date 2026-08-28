# Loophole Audit: SIH PS 26056 — Real-time Airfare Price Index

A systematic review of [project_idea_elaboration.md](file:///Users/shard/projects/VegaBytes_25056/project_idea_elaboration.md) to identify and close every gap that judges, reviewers, or real-world deployment would expose.

---

## Understanding Summary

- **What:** A real-time web-scraping pipeline + statistical index (APIx) that tracks Indian domestic airfare inflation for the NSO/RBI
- **Why:** MoSPI's manual CPI collection cannot keep pace with dynamic airline pricing
- **Who:** Government economists (MoSPI, RBI) — NOT consumers
- **Team:** 6 members across 3 tiers (Data, Logic, Presentation)
- **Deadline:** September 4, 2026
- **Non-goal:** This is NOT a cheap-flight-finder app

---

## 🔴 Critical Loopholes Identified

### Loophole 1: No Legal Defense Framework

> [!CAUTION]
> **Severity: CRITICAL** — A judge asking "Is this legal?" with no prepared answer is an instant credibility killer.

**The Gap:** The document mentions "polite scraping" and respecting `robots.txt`, but has **zero legal framework**. Indian law is ambiguous on scraping — the IT Act 2000 (Sections 43, 66) could be invoked by OTAs, and most OTA Terms of Service explicitly prohibit automated access.

**The Fix — Add to the document:**
1. **Legal Precedent Shield:** Cite the *hiQ Labs v. LinkedIn (2022, US)* ruling — scraping publicly available data is not a CFAA violation. While Indian law differs, this establishes international precedent for statistical research.
2. **"Government Statistical Research" Framing:** Position the project under **MoSPI's mandate** (Collection of Statistics Act, 2008). If MoSPI authorizes this data collection, it has statutory backing. Frame your tool as *something MoSPI would deploy*, not something you're doing rogue.
3. **Technical Compliance Proof:** Log every request with timestamps, show rate-limiting to < 2 req/min, and demonstrate `robots.txt` compliance in your dashboard (a "Compliance Monitor" tab).
4. **Data Minimization:** You only collect *price data* — no PII, no user data, no session data. Make this explicit.

---

### Loophole 2: Uncommitted Statistical Methodology

> [!WARNING]
> **Severity: HIGH** — The index formula choice affects database schema, data collection strategy, and back-testing validity. Deferring this is dangerous.

**The Gap:** The document mentions both Laspeyres and Jevons but commits to neither. The team plans to "let Ankita decide later."

**The Fix — Commit now:**

| Formula | Pros | Cons | Best For |
|---------|------|------|----------|
| **Laspeyres** | Simple, matches CPI methodology used by MoSPI | Overweights base-period patterns (substitution bias) | Alignment with existing govt methodology |
| **Jevons** | Handles substitution, geometric mean dampens outliers | Cannot handle zero prices (sold-out flights = ln(0) = undefined) | Academic rigor |
| **Modified Laspeyres (Recommended)** | Matches MoSPI's actual CPI methodology, easy to back-test against their data | Needs periodic weight updates | **This project** |

**Recommendation:** Use a **Modified Laspeyres Index** with DGCA quarterly traffic data as weights. This directly mirrors how MoSPI calculates the official CPI, making your back-test comparison apples-to-apples. Document this decision explicitly and have Ankita validate it in Sprint 1.

---

### Loophole 3: No Infrastructure Budget or Provider Plan

> [!WARNING]
> **Severity: HIGH** — You cannot collect 30 days of data without infrastructure, and you cannot demo without a running system.

**The Gap:** Residential proxies, cloud compute, and databases cost money. No budget or provider is specified.

**The Fix — Concrete plan:**
1. **Cloud:** Use **GCP Free Tier** (300 USD credits for new accounts) or **Azure for Students** (100 USD). Enough for a small VM + Cloud SQL.
2. **Proxies:** Skip expensive residential proxies for the MVP. Instead:
   - Scrape **airline direct sites** (IndiGo, Akasa, Air India) which have weaker bot protection
   - Use **free rotating datacenter proxies** or **Tor** as a fallback (slower but free)
   - If budget allows, allocate ₹2,000–3,000 for a small residential proxy pool (e.g., BrightData trial)
3. **Database:** Use **Supabase Free Tier** (PostgreSQL) or **Neon Free Tier** — both give you a production Postgres DB at zero cost
4. **Scheduler:** Use **GitHub Actions** (2,000 free minutes/month) as your cron scheduler instead of a dedicated cloud scheduler

---

### Loophole 4: No Demo-Day Failure Strategy

> [!WARNING]
> **Severity: HIGH** — "Use a Kaggle dataset" is transparent and undermines your core value proposition.

**The Gap:** If the scraper fails on demo day (bad Wi-Fi, IP ban, OTA layout change), the backup plan is a static Kaggle dataset. Judges will see through this instantly.

**The Fix — Layered demo strategy:**
1. **Layer 1 (Live):** Run a live scraper against an **airline direct site** (e.g., IndiGo) during the demo. Airline sites have far weaker bot protection than OTAs.
2. **Layer 2 (Pre-warmed):** Have 30 days of **actually scraped data** in your database from your pre-hackathon collection runs. This is real data you collected — not Kaggle.
3. **Layer 3 (Recorded Proof):** Record screen captures of successful scraping runs from the previous weeks. If live fails, show the video + the database entries with timestamps as forensic proof.

> **Resolved (issue #4):** implemented as `docs/demo_day_runbook.md`, exactly as Layers 1-3 above. The original draft here also had a **"Layer 4 — Nuclear Fallback"** (a labeled synthetic dataset if everything else failed). Issue #4 deliberately dropped it: even honestly labeled, fabricated data on stage undercuts the same credibility this whole strategy exists to protect. If Layers 1-3 all fail, the runbook says to state that plainly and pivot to the index methodology and dashboard instead — kept here for the historical record of why it was cut, not as a live plan.

---

### Loophole 5: Base Fare vs. Tax Separation is Handwaved

> [!IMPORTANT]
> **Severity: HIGH** — This is a **specific requirement** of the problem statement and your Q&A answer has a logical flaw.

**The Gap:** Your Q2 answer says "scrape the fixed tax structures (UDF, GST) directly from the Airline's tariff pages." But taxes are NOT fully fixed:
- **GST** is 5% on economy, 12% on business — percentage-based, varies with base fare
- **UDF** varies by airport (DEL UDF ≠ BLR UDF)
- **Fuel surcharges** fluctuate monthly
- **Convenience fees** are OTA-specific and variable

**The Fix:**
1. **Scrape the fare breakdown page**, not just the final price. Most airline direct sites show: Base Fare + Fuel Surcharge + UDF + PSF + GST as separate line items on the booking confirmation preview page.
2. **For OTAs:** Scrape the same route on the airline direct site simultaneously. The OTA total minus airline-direct taxes gives you the OTA's markup/convenience fee as a residual.
3. **Document your tax taxonomy:** Create a lookup table of airport-wise UDF, PSF fees (these are published by AAI) and update it monthly.

---

### Loophole 6: No Data Validation or Quality Framework

> [!IMPORTANT]
> **Severity: MEDIUM** — Garbage in, garbage out. No mention of how you ensure scraped data is correct.

**The Gap:** The document never discusses what happens when the scraper returns wrong data (e.g., scraping a premium economy fare instead of economy, or pulling an international route's price).

**The Fix — Add validation rules:**
1. **Price Range Guards:** Set min/max bounds per route (e.g., DEL-BOM economy: ₹2,000–₹25,000). Anything outside triggers an alert, not an index update.
2. **Cross-Source Validation:** If IndiGo-direct says ₹4,500 but MakeMyTrip says ₹45,000 for the same flight, flag it as a scraping error.
3. **Schema Enforcement:** Every scraped record must contain: `route`, `airline`, `class`, `departure_date`, `scrape_timestamp`, `base_fare`, `total_fare`, `source_url`. Missing fields = rejected row.
4. **Duplicate Detection:** Same flight, same timestamp, same source = dedup.

---

### Loophole 7: The AI DOM Parser Claim is Unproven

> [!NOTE]
> **Severity: MEDIUM** — This is your key innovation differentiator but it's vaporware until demonstrated.

**The Gap:** The document claims you'll "use an LLM (like Gemini or GPT-4o-mini) to dynamically parse raw HTML." This is a strong claim, but:
- LLM API calls cost money per request
- Latency is high (~2–5 seconds per parse vs. milliseconds for CSS selectors)
- Token limits may truncate large HTML pages
- Accuracy is unproven for messy airline HTML

**The Fix:**
1. **Primary:** Use traditional CSS/XPath selectors — they're fast and free
2. **Fallback:** When selectors fail (detected by empty/malformed output), trigger the LLM parser on just the **relevant HTML fragment** (not the full page), keeping costs and latency low
3. **Proof of Concept:** Build a 5-minute demo showing: "Here's the page before a DOM change → selector breaks → LLM parser recovers the price." This is your killer demo moment.
4. **Budget:** Use Gemini Flash (free tier: 15 RPM) for the fallback parser — zero cost for the MVP.

---

### Loophole 8: No Monitoring, Alerting, or Observability

> [!NOTE]
> **Severity: MEDIUM** — Your scraper runs 24/7 for 30 days. How do you know when it breaks at 3 AM?

**The Gap:** No mention of how the team monitors pipeline health.

**The Fix:**
1. **Health Dashboard:** Add a simple "Pipeline Status" panel to your dashboard showing: last successful scrape timestamp, success/failure ratio, data freshness per route.
2. **Alerting:** Use a free Telegram/Discord bot to send alerts when: scraper fails 3x consecutively, no data received in 6 hours, or price anomaly detected.
3. **Logging:** Every scraper run must log: start time, end time, rows scraped, errors encountered, proxy used.

---

### Loophole 9: Missing Unanswered Judge Questions

> [!NOTE]
> **Severity: MEDIUM** — Your Q&A section covers 3 questions but misses several obvious follow-ups.

**Missing Questions to Prepare:**

**Q4. "How does your index handle seasonal routes that don't operate year-round?"**
- Answer: "We classify routes as 'perennial' (DEL-BOM) vs 'seasonal' (DEL-LEH). Seasonal routes are excluded from the base index and tracked in a supplementary seasonal sub-index to prevent artificial deflation when they disappear."

**Q5. "What's your data retention and privacy policy?"**
- Answer: "No PII is intentionally collected or stored. We store only aggregated fare data points — no user sessions, no cookies, no personal information. Data is retained for 2 years for back-testing purposes, aligned with MoSPI's data archival norms."

**Q6. "How do you handle multi-stop flights and codeshares?"**
- Answer: "We restrict our index to non-stop, direct flights only. Codeshares are deduplicated by matching the operating carrier's flight number. This ensures price purity — a codeshare markup would distort the base fare signal."

**Q7. "Can your system scale beyond airfares?"**
- Answer: "Yes. Our architecture is source-agnostic. The scraper factory pattern means adding Amazon product prices or Ola ride fares requires only a new parser plugin — zero changes to the index engine, database, or dashboard."

---

## Assumptions (Documented)

1. The team has access to student cloud credits (GCP/Azure/AWS) — **unconfirmed**
2. Airline direct sites (IndiGo, Akasa) have weaker bot protection than OTAs — **reasonable but needs verification**
3. DGCA traffic data is current and publicly downloadable — **confirmed, available at dgca.gov.in**
4. The SIH evaluation permits web scraping as a methodology — **assumed based on problem statement wording**
5. The team can start scraping ≥30 days before the finale — **depends on September 4 deadline and current date**

---

## Decision Log

| # | Decision | Alternatives Considered | Rationale |
|---|----------|------------------------|-----------|
| 1 | Use Modified Laspeyres Index | Jevons, Fisher, Törnqvist | Matches MoSPI's actual CPI methodology; enables direct back-test comparison |
| 2 | Primary: CSS selectors, Fallback: LLM parser | LLM-only, Regex-only | Cost-effective, fast primary path with intelligent fallback |
| 3 | Scrape airline direct sites as primary, OTAs as secondary | OTA-first approach | Lower bot-protection risk, native fare breakdowns available |
| 4 | Use free-tier cloud (GCP/Supabase/GitHub Actions) | Paid infrastructure | Student hackathon budget constraint |
| 5 | 3-layer demo strategy (live + pre-collected + recorded) | Live-only, Kaggle fallback | Resilient demo that proves real capability at every failure level |

---

## Proposed Changes to [project_idea_elaboration.md](file:///Users/shard/projects/VegaBytes_25056/project_idea_elaboration.md)

### Section Updates

#### [MODIFY] Section 2 — Feasibility of Execution
- Add infrastructure budget plan (free-tier cloud stack)
- Add legal defensibility framework

#### [MODIFY] Section 4 — Scope of Innovation
- Commit to Modified Laspeyres formula instead of listing both
- Clarify AI DOM parser as a fallback, not primary

#### [MODIFY] Section 6 — Evaluator's Perspective
- Add data validation framework (price guards, cross-source validation)
- Add monitoring/alerting requirements

#### [MODIFY] Section 9 — Data & Resource Availability
- ✅ Done (issue #4): replaced the Kaggle backup plan with a pointer to `docs/demo_day_runbook.md`'s layered demo strategy
- Add concrete infrastructure provider choices

#### [MODIFY] Section 10 — Judge Q&A
- Fix the tax separation answer (Q2) to acknowledge variable taxes
- Add Q4–Q7 with prepared answers

#### [MODIFY] Tier 1 Role Description
- Add monitoring/alerting as Mukta's responsibility
- Add data validation as Shardul's responsibility

---

## Verification Plan

### Manual Verification
- Review each fix against the original problem statement requirements
- Cross-check the Modified Laspeyres recommendation against MoSPI's published CPI methodology document
- Validate that the demo strategy covers all realistic failure modes
- Confirm free-tier limits of recommended cloud providers are sufficient

> Does this accurately reflect your intent?
> Please confirm or correct anything before I apply these fixes to the document.

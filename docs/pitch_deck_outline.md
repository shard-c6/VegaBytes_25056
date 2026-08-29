# 🛫 VegaBytes — Pitch Deck Outline & Presentation Narrative
## SIH Problem Statement 26056: Real-time Airfare Price Index for India

---

## 🎯 1. Elevator Pitch (30 Seconds)
"The Reserve Bank of India and MoSPI currently rely on lagging, manual surveys to measure airfare inflation. But in a world of algorithmic surge pricing, airline fares fluctuate by 200–400% in a single day. 
**VegaBytes** delivers a real-time, automated economic data pipeline that scrapes, validates, and indexes Indian domestic airfares — giving policymakers high-frequency inflation signals using the Modified Laspeyres Index."

---

## 📊 2. Slide Structure & Narrative Flow (5-7 Minutes)

### Slide 1: The Problem — Lagging Data in an Algorithmic World
- **Current NSO Process**: Manual monthly sampling, periodic physical collection.
- **Market Reality**: Over 90% of tickets are dynamic online sales (OTAs & direct portals).
- **Economic Cost**: Lagged CPI metrics lead to sub-optimal RBI monetary policy decisions.

### Slide 2: Inspiration & Validation
- **MIT Billion Prices Project (Cavallo & Rigobon)**: Proved online scraped data tracks inflation weeks faster than traditional government surveys.
- **VegaBytes Goal**: Bring this methodology to India's aviation transport sector.

### Slide 3: 3-Tier System Architecture
- **Tier 1 (Data Layer)**: Stealth Playwright scrapers + Gemini Flash AI DOM fallback + strict rate-limiting (<2 req/min) & zero PII.
- **Tier 2 (Logic Layer)**: Base fare vs. tax isolation (UDF, GST, fuel surcharge) + Modified Laspeyres Index calculation with DGCA passenger weights.
- **Tier 3 (Presentation Layer)**: Real-time interactive dashboard + REST APIs for NSO/RBI integration.

### Slide 4: Mathematical Rigor & Base Fare Isolation
- Why simple averages fail: Demand weighting via DGCA quarterly route data.
- Tax extraction: Deducting fixed airport fees to isolate pure base fare elasticities.
- Handling outliers & sold-out flights (Carry-Forward Imputation).

### Slide 5: Interactive Dashboard Demo
- Live APIx index vs. MoSPI historical back-test.
- Sector heatmaps & high-frequency route price trends.
- Pipeline health & statutory compliance monitor.

### Slide 6: Legal Defensibility & Scalability
- **Legal**: Collection of Statistics Act (2008) framework, *hiQ Labs v. LinkedIn* precedent, `robots.txt` compliance.
- **Scalability**: Factory-pattern architecture ready to scale to hotels, railways, and e-commerce.

---

## 🎤 3. Expected Judge Q&A Handling

| Question Area | Lead Speaker | Key Defense Point |
|---------------|--------------|-------------------|
| **Macroeconomic Impact & Strategy** | **Shubham** | High-frequency CPI forecasting, RBI policy alignment, MIT BPP methodology |
| **Legal & Bot Scraping Ethics** | **Shubham / Shardul** | Polite scraping, <2 req/min, zero PII, statutory statistical research |
| **Technical Architecture / Scraping** | **Shardul** | AI DOM Parser fallback, Playwright stealth, proxy rotation |
| **Index Math & Outliers** | **Ankita** | Modified Laspeyres formula, DGCA weights, carry-forward imputation |

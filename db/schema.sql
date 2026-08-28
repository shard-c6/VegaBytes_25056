-- ============================================================
-- VegaBytes APIx — Database Schema
-- SIH PS 26056: Real-time Airfare Price Index
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Routes reference table ───────────────────────────────
CREATE TABLE IF NOT EXISTS routes (
    id          SERIAL PRIMARY KEY,
    origin      CHAR(3) NOT NULL,          -- IATA code e.g. DEL
    destination CHAR(3) NOT NULL,          -- IATA code e.g. BOM
    label       VARCHAR(30) GENERATED ALWAYS AS (origin || '-' || destination) STORED,
    dgca_weight NUMERIC(6,4) NOT NULL DEFAULT 0, -- Laspeyres weight from DGCA traffic data
    is_seasonal BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(origin, destination)
);

-- ── Raw scraped fares ────────────────────────────────────
CREATE TABLE IF NOT EXISTS scraped_fares (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    route_id        INTEGER NOT NULL REFERENCES routes(id),
    airline         VARCHAR(50) NOT NULL,
    flight_number   VARCHAR(10),
    cabin_class     VARCHAR(20) NOT NULL DEFAULT 'economy',
    departure_date  DATE NOT NULL,
    booking_window  INTEGER NOT NULL,      -- days ahead: 1, 7, 30
    base_fare       NUMERIC(10,2),         -- isolated base fare in INR
    fuel_surcharge  NUMERIC(10,2),
    udf             NUMERIC(10,2),         -- User Development Fee (airport-specific)
    psf             NUMERIC(10,2),         -- Passenger Service Fee
    gst             NUMERIC(10,2),
    total_fare      NUMERIC(10,2) NOT NULL,
    source          VARCHAR(50) NOT NULL,  -- e.g. 'indigo_direct', 'makemytrip'
    source_url      TEXT,
    raw_html_path   TEXT,                  -- gzipped archive of the scraped page, see src/scrapers/base.py:archive_html
    scrape_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_valid        BOOLEAN NOT NULL DEFAULT TRUE
);

-- Additive migration: re-running this file against a database created before
-- raw_html_path existed adds the column instead of silently no-op'ing (Postgres
-- 9.6+; CREATE TABLE IF NOT EXISTS above does not add columns to an existing table).
ALTER TABLE scraped_fares ADD COLUMN IF NOT EXISTS raw_html_path TEXT;

CREATE INDEX idx_scraped_fares_route_date ON scraped_fares(route_id, departure_date);
CREATE INDEX idx_scraped_fares_timestamp  ON scraped_fares(scrape_timestamp DESC);

-- ── Data quality log ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS data_quality_log (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    route_id        INTEGER REFERENCES routes(id),
    source          VARCHAR(50),
    rejection_reason VARCHAR(200) NOT NULL,
    raw_value       TEXT,
    scrape_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Computed index values ────────────────────────────────
CREATE TABLE IF NOT EXISTS index_values (
    id              SERIAL PRIMARY KEY,
    index_date      DATE NOT NULL UNIQUE,
    apix_value      NUMERIC(10,4) NOT NULL,  -- Modified Laspeyres Index value
    base_period     DATE NOT NULL,            -- Reference base period
    routes_included INTEGER NOT NULL,
    notes           TEXT,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Scraper run logs ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS scraper_runs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source          VARCHAR(50) NOT NULL,
    started_at      TIMESTAMPTZ NOT NULL,
    finished_at     TIMESTAMPTZ,
    rows_scraped    INTEGER DEFAULT 0,
    rows_rejected   INTEGER DEFAULT 0,
    error_message   TEXT,
    proxy_used      VARCHAR(100),  -- masked
    status          VARCHAR(20) NOT NULL DEFAULT 'running' -- running | success | failed
);

-- ── Seed: initial routes (top-5 DGCA routes, weights TBD by Ankita) ──
INSERT INTO routes (origin, destination, dgca_weight, is_seasonal) VALUES
  ('DEL', 'BOM', 0.0, FALSE),
  ('BLR', 'DEL', 0.0, FALSE),
  ('DEL', 'BLR', 0.0, FALSE),
  ('BOM', 'BLR', 0.0, FALSE),
  ('HYD', 'DEL', 0.0, FALSE)
ON CONFLICT DO NOTHING;

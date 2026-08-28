"""
Persistence layer — SQLAlchemy Core.

Talks to Postgres in production (schema applied via `db/schema.sql`, which
stays canonical there) or a local SQLite file for development. SQLite can't
run schema.sql verbatim (it uses `uuid-ossp` and a Postgres `GENERATED ALWAYS
AS ... STORED` column), so the table shapes are declared here in a
dialect-portable way and created on demand via `ensure_schema()`.

Deliberately Core, not a declarative ORM — this project has no need for
model classes, relationships, or migrations (see docs/architecture.md).

Owner: Shardul
Related Issue: #17
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import (
    Boolean,
    Column,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    insert,
    select,
    text,
)
from sqlalchemy.engine import Connection, Engine

from .scrapers.base import FareRecord

log = structlog.get_logger()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///vegabytes.db")

engine: Engine = create_engine(DATABASE_URL, future=True)
metadata = MetaData()

routes = Table(
    "routes",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("origin", String(3), nullable=False),
    Column("destination", String(3), nullable=False),
    # Generated on both dialects (Postgres via db/schema.sql's identical
    # expression, SQLite via this Computed()) — never supplied on INSERT.
    Column("label", String(30), Computed("origin || '-' || destination", persisted=True)),
    Column("dgca_weight", Float, nullable=False, default=0.0),
    Column("is_seasonal", Boolean, nullable=False, default=False),
    Column("created_at", DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)),
    UniqueConstraint("origin", "destination", name="uq_routes_origin_destination"),
)

scraped_fares = Table(
    "scraped_fares",
    metadata,
    Column("id", String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
    Column("route_id", Integer, ForeignKey("routes.id"), nullable=False),
    Column("airline", String(50), nullable=False),
    Column("flight_number", String(10)),
    Column("cabin_class", String(20), nullable=False, default="economy"),
    Column("departure_date", Date, nullable=False),
    Column("booking_window", Integer, nullable=False),
    Column("base_fare", Float),
    Column("fuel_surcharge", Float),
    Column("udf", Float),
    Column("psf", Float),
    Column("gst", Float),
    Column("total_fare", Float, nullable=False),
    Column("source", String(50), nullable=False),
    Column("source_url", Text),
    Column("raw_html_path", Text),
    Column(
        "scrape_timestamp", DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    ),
    Column("is_valid", Boolean, nullable=False, default=True),
)

data_quality_log = Table(
    "data_quality_log",
    metadata,
    Column("id", String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
    Column("route_id", Integer, ForeignKey("routes.id")),
    Column("source", String(50)),
    Column("rejection_reason", String(200), nullable=False),
    Column("raw_value", Text),
    Column(
        "scrape_timestamp", DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    ),
)

scraper_runs = Table(
    "scraper_runs",
    metadata,
    Column("id", String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
    Column("source", String(50), nullable=False),
    Column("started_at", DateTime, nullable=False),
    Column("finished_at", DateTime),
    Column("rows_scraped", Integer, default=0),
    Column("rows_rejected", Integer, default=0),
    Column("error_message", Text),
    Column("proxy_used", String(100)),
    Column("status", String(20), nullable=False, default="running"),
)

# Mirrors the seed data in db/schema.sql — weights are TBD (see issue #2).
_SEED_ROUTES = [
    ("DEL", "BOM"),
    ("BLR", "DEL"),
    ("DEL", "BLR"),
    ("BOM", "BLR"),
    ("HYD", "DEL"),
]


def _add_missing_sqlite_columns(conn: Connection) -> None:
    """
    SQLite-only additive migration.

    `metadata.create_all()` only creates tables that don't exist yet — it
    never adds columns to a table that's already there. A SQLite file created
    before `raw_html_path` existed would otherwise reject every fare insert.
    Postgres has the equivalent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` in
    db/schema.sql.
    """
    if conn.engine.dialect.name != "sqlite":
        return
    existing_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(scraped_fares)"))}
    if "raw_html_path" not in existing_cols:
        conn.execute(text("ALTER TABLE scraped_fares ADD COLUMN raw_html_path TEXT"))
        conn.commit()


def ensure_schema(conn: Optional[Connection] = None) -> None:
    """Create tables if missing (SQLite dev convenience) and seed routes.

    On Postgres this is a no-op for tables `db/schema.sql` already created;
    it only fills in routes that aren't there yet.
    """
    metadata.create_all(engine)
    owns_conn = conn is None
    conn = conn or engine.connect()
    try:
        _add_missing_sqlite_columns(conn)
        existing = {
            (row.origin, row.destination)
            for row in conn.execute(select(routes.c.origin, routes.c.destination))
        }
        # `label` is a generated column on both dialects (see the routes Table
        # def above) — never supplied here, the DB computes it.
        missing = [
            {
                "origin": o,
                "destination": d,
                "dgca_weight": 0.0,
                "is_seasonal": False,
            }
            for o, d in _SEED_ROUTES
            if (o, d) not in existing
        ]
        if missing:
            conn.execute(insert(routes), missing)
            conn.commit()
    finally:
        if owns_conn:
            conn.close()


def get_route_id(conn: Connection, origin: str, destination: str) -> Optional[int]:
    row = conn.execute(
        select(routes.c.id).where(routes.c.origin == origin, routes.c.destination == destination)
    ).first()
    return row[0] if row else None


def insert_scraped_fares(conn: Connection, records: list[FareRecord]) -> int:
    """Insert valid records. Returns the number of rows actually written."""
    rows = []
    for r in records:
        origin, _, destination = r.route.partition("-")
        route_id = get_route_id(conn, origin, destination)
        if route_id is None:
            log.warning("unknown_route_skipped", route=r.route, source=r.source)
            continue
        rows.append(
            {
                "route_id": route_id,
                "airline": r.airline,
                "flight_number": r.flight_number,
                "cabin_class": r.cabin_class,
                "departure_date": r.departure_date,
                "booking_window": r.booking_window,
                "base_fare": r.base_fare,
                "fuel_surcharge": r.fuel_surcharge,
                "udf": r.udf,
                "psf": r.psf,
                "gst": r.gst,
                "total_fare": r.total_fare,
                "source": r.source,
                "source_url": r.source_url,
                "raw_html_path": r.raw_html_path,
            }
        )
    if rows:
        conn.execute(insert(scraped_fares), rows)
        conn.commit()
    return len(rows)


def insert_rejections(conn: Connection, source: str, rejections: list[dict]) -> int:
    """Insert rejected rows (as produced by PriceValidator.validate_batch)."""
    rows = []
    for rej in rejections:
        route_id = None
        route = rej.get("route")
        if route:
            origin, _, destination = route.partition("-")
            route_id = get_route_id(conn, origin, destination)
        rows.append(
            {
                "route_id": route_id,
                "source": rej.get("source", source),
                "rejection_reason": rej["rejection_reason"],
                "raw_value": str(rej.get("total_fare")),
            }
        )
    if rows:
        conn.execute(insert(data_quality_log), rows)
        conn.commit()
    return len(rows)


def start_scraper_run(conn: Connection, source: str) -> str:
    run_id = str(uuid.uuid4())
    conn.execute(
        insert(scraper_runs).values(
            id=run_id,
            source=source,
            started_at=datetime.now(timezone.utc),
            status="running",
        )
    )
    conn.commit()
    return run_id


def finish_scraper_run(
    conn: Connection,
    run_id: str,
    status: str,
    rows_scraped: int = 0,
    rows_rejected: int = 0,
    error_message: Optional[str] = None,
) -> None:
    conn.execute(
        scraper_runs.update()
        .where(scraper_runs.c.id == run_id)
        .values(
            finished_at=datetime.now(timezone.utc),
            status=status,
            rows_scraped=rows_scraped,
            rows_rejected=rows_rejected,
            error_message=error_message,
        )
    )
    conn.commit()

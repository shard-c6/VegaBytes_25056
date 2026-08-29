"""
Tests for PriceValidator — Issue #6.
Run: pytest tests/test_validator.py -v
"""

from datetime import date

from src.etl.validator import PriceValidator
from src.scrapers.base import FareRecord


def make_record(**kwargs) -> FareRecord:
    defaults = dict(
        route="DEL-BOM",
        airline="IndiGo",
        flight_number="6E-123",
        cabin_class="economy",
        departure_date=date(2026, 9, 1),
        booking_window=7,
        base_fare=3500.0,
        fuel_surcharge=500.0,
        udf=None,
        psf=None,
        gst=None,
        total_fare=4200.0,
        source="indigo_direct",
        source_url=None,
    )
    defaults.update(kwargs)
    return FareRecord(**defaults)  # type: ignore[arg-type]


validator = PriceValidator()


def test_valid_record_passes():
    assert validator.validate(make_record()).is_valid


def test_zero_total_fare_rejected():
    result = validator.validate(make_record(total_fare=0))
    assert not result.is_valid
    assert "total_fare" in result.reason


def test_fare_above_upper_bound_rejected():
    result = validator.validate(make_record(total_fare=99_999))
    assert not result.is_valid
    assert "bounds" in result.reason


def test_fare_below_lower_bound_rejected():
    result = validator.validate(make_record(total_fare=100))
    assert not result.is_valid


def test_base_fare_exceeds_total_rejected():
    result = validator.validate(make_record(base_fare=9000.0, total_fare=5000.0))
    assert not result.is_valid
    assert "base_fare" in result.reason


def test_invalid_cabin_class_rejected():
    result = validator.validate(make_record(cabin_class="first"))
    assert not result.is_valid


def test_batch_validation_splits_correctly():
    records = [
        make_record(total_fare=4200.0),  # valid
        make_record(total_fare=0),  # invalid
        make_record(total_fare=99_999),  # invalid
    ]
    valid, rejected = validator.validate_batch(records)
    assert len(valid) == 1
    assert len(rejected) == 2

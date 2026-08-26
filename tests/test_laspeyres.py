"""
Tests for LaspeyresIndexCalculator — Issue #2.
Run: pytest tests/test_laspeyres.py -v
"""
from datetime import date
import pytest
from src.index.laspeyres import LaspeyresIndexCalculator, RouteWeight


BASE_DATE = date(2026, 8, 1)
WEIGHTS = [
    RouteWeight("DEL-BOM", 0.30),
    RouteWeight("BLR-DEL", 0.25),
    RouteWeight("DEL-BLR", 0.25),
    RouteWeight("BOM-BLR", 0.20),
]
BASE_FARES = {"DEL-BOM": 3500.0, "BLR-DEL": 3200.0, "DEL-BLR": 3100.0, "BOM-BLR": 2800.0}


@pytest.fixture
def calculator():
    calc = LaspeyresIndexCalculator(weights=WEIGHTS, base_period=BASE_DATE)
    calc.set_base_fares(BASE_FARES)
    return calc


def test_index_equals_100_at_base_period(calculator):
    result = calculator.compute(BASE_FARES, BASE_DATE)
    assert abs(result.apix_value - 100.0) < 0.01


def test_index_above_100_when_fares_rise(calculator):
    higher_fares = {k: v * 1.10 for k, v in BASE_FARES.items()}
    result = calculator.compute(higher_fares, date(2026, 9, 1))
    assert result.apix_value > 100.0
    assert abs(result.apix_value - 110.0) < 0.5


def test_carry_forward_on_missing_route(calculator):
    partial_fares = dict(BASE_FARES)
    del partial_fares["BOM-BLR"]
    result = calculator.compute(partial_fares, date(2026, 9, 1))
    assert "BOM-BLR" in result.routes_missing
    assert result.routes_included == 4  # carry-forward still includes it


def test_raises_without_base_fares():
    calc = LaspeyresIndexCalculator(weights=WEIGHTS, base_period=BASE_DATE)
    with pytest.raises(RuntimeError, match="Base fares not loaded"):
        calc.compute(BASE_FARES, date(2026, 9, 1))

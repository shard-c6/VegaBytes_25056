"""
Tests for AIdomParser — Issue #17.
Run: GEMINI_API_KEY=dummy pytest tests/test_ai_dom_parser.py -v

The Gemini client itself is mocked throughout — these tests exercise
response handling (API failures, malformed JSON, malformed shapes,
malformed fare values), not the live API.
"""

from datetime import date
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from src.scrapers.ai_dom_parser import AIdomParser, _strip_noise


@pytest.fixture(autouse=True)
def gemini_api_key(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")


@pytest.fixture
def parser(gemini_api_key):
    return AIdomParser()


@pytest.fixture
def context():
    return {
        "source": "indigo_direct",
        "origin": "DEL",
        "destination": "BOM",
        "departure_date": date(2026, 9, 1),
        "booking_window": 7,
    }


def test_model_name_falls_back_when_env_var_blank(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "")
    assert AIdomParser().model_name == "gemini-2.5-flash"


def test_model_name_honors_env_var_override(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-custom")
    assert AIdomParser().model_name == "gemini-custom"


def test_short_fragment_returns_empty_without_calling_api(parser, context):
    with patch.object(parser._client.models, "generate_content") as mock_call:
        assert parser.parse("short", context) == []
        mock_call.assert_not_called()


def test_api_failure_returns_empty(parser, context):
    with patch.object(parser._client.models, "generate_content", side_effect=RuntimeError("boom")):
        assert parser.parse("<div>" + "x" * 60 + "</div>", context) == []


def test_non_text_response_returns_empty(parser, context):
    mock_resp = MagicMock()
    type(mock_resp).text = PropertyMock(side_effect=ValueError("non-text parts"))
    with patch.object(parser._client.models, "generate_content", return_value=mock_resp):
        assert parser.parse("<div>" + "x" * 60 + "</div>", context) == []


def test_malformed_json_returns_empty(parser, context):
    mock_resp = MagicMock()
    mock_resp.text = "not json at all"
    with patch.object(parser._client.models, "generate_content", return_value=mock_resp):
        assert parser.parse("<div>" + "x" * 60 + "</div>", context) == []


@pytest.mark.parametrize("raw", ['{"airline": "IndiGo"}', "[1, 2, 3]", '"a string"'])
def test_invalid_shape_returns_empty(parser, context, raw):
    mock_resp = MagicMock()
    mock_resp.text = raw
    with patch.object(parser._client.models, "generate_content", return_value=mock_resp):
        assert parser.parse("<div>" + "x" * 60 + "</div>", context) == []


def test_fenced_json_response_parses_correctly(parser, context):
    mock_resp = MagicMock()
    mock_resp.text = (
        '```json\n[{"airline": "IndiGo", "total_fare": 4500, ' '"flight_number": "6E123"}]\n```'
    )
    with patch.object(parser._client.models, "generate_content", return_value=mock_resp):
        result = parser.parse("<div>" + "x" * 60 + "</div>", context)
    assert len(result) == 1
    assert result[0].total_fare == 4500.0
    assert result[0].flight_number == "6E123"


def test_bool_and_nan_fares_skipped_valid_records_kept(parser, context):
    mock_resp = MagicMock()
    mock_resp.text = (
        '[{"airline": "IndiGo", "total_fare": true, "flight_number": "6E1"}, '
        '{"airline": "IndiGo", "total_fare": NaN, "flight_number": "6E2"}, '
        '{"airline": "IndiGo", "total_fare": 4500, "flight_number": "6E3"}]'
    )
    with patch.object(parser._client.models, "generate_content", return_value=mock_resp):
        result = parser.parse("<div>" + "x" * 60 + "</div>", context)
    assert [r.flight_number for r in result] == ["6E3"]


def test_malformed_airline_and_cabin_class_rejected(parser, context):
    mock_resp = MagicMock()
    mock_resp.text = (
        '[{"airline": {"name": "X"}, "total_fare": 4500, "flight_number": "6E1"}, '
        '{"airline": "IndiGo", "cabin_class": "first", "total_fare": 4500, "flight_number": "6E2"}, '
        '{"airline": "IndiGo", "total_fare": 4500, "flight_number": "6E3"}]'
    )
    with patch.object(parser._client.models, "generate_content", return_value=mock_resp):
        result = parser.parse("<div>" + "x" * 60 + "</div>", context)
    assert [r.flight_number for r in result] == ["6E3"]


def test_strip_noise_removes_script_style_form_input():
    html = (
        '<div><script>evil()</script><form><input name="csrf" value="secret123">'
        "</form><style>.x{}</style><p>IndiGo &#8377;4500</p></div>"
    )
    result = _strip_noise(html)
    assert "evil" not in result
    assert "secret123" not in result
    assert "IndiGo" in result

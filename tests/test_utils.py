import pytest
from datetime import datetime
from utils.helpers import parse_tags, validate_price, parse_date, format_price, get_week_range, get_month_range, escape_markdown
from config import DATE_FORMAT


def test_parse_tags_basic():
    assert parse_tags("a, b, c") == ["a", "b", "c"]
    assert parse_tags(" A , B ") == ["a", "b"]
    assert parse_tags("") == []


def test_validate_price():
    assert validate_price("1500") == 1500.0
    assert validate_price("1,500.50") == 1500.5
    assert validate_price("1 500,50") == 1500.5
    assert validate_price("-5") is None
    assert validate_price("") is None


def test_parse_date():
    assert parse_date("01.09.2025") == datetime.strptime("01.09.2025", DATE_FORMAT)
    assert parse_date("31-12-2025") is None


def test_format_price():
    assert format_price(1000.0) == "1 000 ₽"
    assert format_price(1000.5) == "1 000.50 ₽"


def test_week_month_ranges():
    start, end = get_week_range()
    assert start <= end
    ms, me = get_month_range()
    assert ms <= me


def test_escape_markdown():
    text = "[link](url) *bold* _it_"
    escaped = escape_markdown(text)
    assert "\\[" in escaped and "\\]" in escaped
    assert "\\*" in escaped and "\\_" in escaped

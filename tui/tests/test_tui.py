import pytest
import datetime
from tui import get_default_days, parse_arguments, matches_filter

def test_get_default_days():
    # Monday is weekday 0
    monday = datetime.date(2026, 6, 22)
    assert get_default_days(monday) == 2
    
    # Tuesday is weekday 1
    tuesday = datetime.date(2026, 6, 23)
    assert get_default_days(tuesday) == 1
    
    # Sunday is weekday 6
    sunday = datetime.date(2026, 6, 28)
    assert get_default_days(sunday) == 1

def test_parse_arguments_defaults():
    # Test default day logic within parse_arguments
    # Note: today could be Monday or not, so we check if result matches the actual weekday expectation
    parsed = parse_arguments([])
    assert parsed.sa == ""
    assert parsed.sn == ""
    expected_days = get_default_days()
    assert parsed.days == expected_days

def test_parse_arguments_custom():
    parsed = parse_arguments(["MyApp", "12345", "--days", "5"])
    assert parsed.sa == "MyApp"
    assert parsed.sn == "12345"
    assert parsed.days == 5

def test_parse_arguments_invalid_sn():
    with pytest.raises(SystemExit):
        parse_arguments(["MyApp", "123a45"])

def test_matches_filter_dict():
    item = {"sa": "MyApplication", "sn": "987654"}
    
    # Matching empty filters
    assert matches_filter(item, "", "") is True
    
    # Matching correct filters
    assert matches_filter(item, "app", "876") is True
    assert matches_filter(item, "MYAPPLICATION", "987654") is True
    
    # Mismatching SA
    assert matches_filter(item, "other", "") is False
    
    # Mismatching SN
    assert matches_filter(item, "", "111") is False

def test_matches_filter_object():
    class TestItem:
        def __init__(self, sa, sn):
            self.sa = sa
            self.sn = sn
            
    item = TestItem("SystemA", "555123")
    
    assert matches_filter(item, "system", "123") is True
    assert matches_filter(item, "sys", "555") is True
    assert matches_filter(item, "systemb", "123") is False
    assert matches_filter(item, "system", "444") is False

def test_matches_filter_string():
    item = "Device-SA-1234-SN-5678"
    
    assert matches_filter(item, "device", "5678") is True
    assert matches_filter(item, "sa-123", "") is True
    assert matches_filter(item, "nonexistent", "") is False

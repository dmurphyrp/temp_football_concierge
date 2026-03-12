"""Tests for tools/add_to_calendar.py.

This tool is pure logic with no external calls — no mocking required.
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_concierge.tools.add_to_calendar import add_to_calendar

_TITLE = "Arsenal vs Spurs — Pitch & Pint"
_START = "2026-03-14T17:30:00Z"
_LOCATION = "12 Football Lane, London"


class TestAddToCalendar:
    def test_valid_event_returns_success(self):
        result = add_to_calendar(_TITLE, _START, _LOCATION)
        assert result["status"] == "success"

    def test_event_id_is_generated(self):
        result = add_to_calendar(_TITLE, _START, _LOCATION)
        assert "event_id" in result
        assert result["event_id"].startswith("CAL-")

    def test_event_title_is_echoed(self):
        result = add_to_calendar(_TITLE, _START, _LOCATION)
        assert result["event_title"] == _TITLE

    def test_location_is_echoed(self):
        result = add_to_calendar(_TITLE, _START, _LOCATION)
        assert result["location"] == _LOCATION

    def test_start_time_is_echoed(self):
        result = add_to_calendar(_TITLE, _START, _LOCATION)
        assert result["start_utc"] == _START

    def test_end_time_is_3_hours_after_start(self):
        result = add_to_calendar(_TITLE, _START, _LOCATION)
        start = datetime.datetime.fromisoformat(_START.replace("Z", "+00:00"))
        end = datetime.datetime.fromisoformat(
            result["end_utc"].replace("Z", "+00:00")
        )
        assert (end - start).total_seconds() == 3 * 3600

    def test_calendar_link_is_a_google_url(self):
        result = add_to_calendar(_TITLE, _START, _LOCATION)
        assert result["calendar_link"].startswith("https://calendar.google.com")

    def test_calendar_link_contains_title_text(self):
        result = add_to_calendar(_TITLE, _START, _LOCATION)
        assert "Arsenal" in result["calendar_link"]

    def test_description_is_included_when_provided(self):
        result = add_to_calendar(
            _TITLE, _START, _LOCATION,
            description="Booking ref MC-00001. Liam, Seán attending."
        )
        assert "Booking ref" in result["description"]

    def test_description_defaults_to_empty_string(self):
        result = add_to_calendar(_TITLE, _START, _LOCATION)
        assert result["description"] == ""

    def test_invalid_start_time_returns_error(self):
        result = add_to_calendar(_TITLE, "not-a-date", _LOCATION)
        assert result["status"] == "error"

    def test_event_id_is_deterministic(self):
        r1 = add_to_calendar(_TITLE, _START, _LOCATION)
        r2 = add_to_calendar(_TITLE, _START, _LOCATION)
        assert r1["event_id"] == r2["event_id"]

    def test_confirmation_message_is_present(self):
        result = add_to_calendar(_TITLE, _START, _LOCATION)
        assert "confirmation" in result
        assert len(result["confirmation"]) > 0

"""Tests for tools/book_table.py.

This tool is pure logic with no external calls — no mocking required.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_concierge.tools.book_table import book_table
from event_concierge.tools.check_bar_availability import _SIMULATED_CAPACITY

_KICKOFF = "2026-03-14T17:30:00Z"


class TestBookTable:
    def test_valid_booking_returns_success(self):
        result = book_table("Pitch & Pint", 4, _KICKOFF)
        assert result["status"] == "success"

    def test_booking_reference_is_generated(self):
        result = book_table("Pitch & Pint", 2, _KICKOFF)
        assert "booking_reference" in result
        assert result["booking_reference"].startswith("MC-")

    def test_booking_confirms_venue_name(self):
        result = book_table("The Anchor", 3, _KICKOFF)
        assert result["venue"] == "The Anchor"

    def test_booking_confirms_party_size(self):
        result = book_table("The Anchor", 6, _KICKOFF)
        assert result["party_size"] == 6

    def test_booking_confirms_match_time(self):
        result = book_table("Any Bar", 4, _KICKOFF)
        assert result["match_time"] == _KICKOFF

    def test_booking_at_capacity_succeeds(self):
        result = book_table("Any Bar", _SIMULATED_CAPACITY, _KICKOFF)
        assert result["status"] == "success"

    def test_party_over_capacity_returns_error(self):
        result = book_table("Any Bar", _SIMULATED_CAPACITY + 1, _KICKOFF)
        assert result["status"] == "error"
        assert "error_message" in result

    def test_empty_venue_name_returns_error(self):
        result = book_table("", 4, _KICKOFF)
        assert result["status"] == "error"

    def test_booking_reference_is_deterministic(self):
        r1 = book_table("Pitch & Pint", 4, _KICKOFF)
        r2 = book_table("Pitch & Pint", 4, _KICKOFF)
        assert r1["booking_reference"] == r2["booking_reference"]

    def test_different_venues_produce_different_references(self):
        r1 = book_table("Bar A", 2, _KICKOFF)
        r2 = book_table("Bar B", 2, _KICKOFF)
        assert r1["booking_reference"] != r2["booking_reference"]

    def test_works_with_any_venue_name(self):
        result = book_table("A Real Google Maps Bar", 5, _KICKOFF)
        assert result["status"] == "success"

"""Tests for tools/check_bar_availability.py.

This tool is pure logic with no external calls — no mocking required.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_concierge.tools.check_bar_availability import (
    check_bar_availability,
    _SIMULATED_CAPACITY,
)

_KICKOFF = "2026-03-14T17:30:00Z"


class TestCheckBarAvailability:
    def test_small_group_can_accommodate(self):
        result = check_bar_availability("Pitch & Pint", 4, _KICKOFF)
        assert result["status"] == "success"
        assert result["can_accommodate"] is True

    def test_group_at_capacity_can_accommodate(self):
        result = check_bar_availability("The Anchor", _SIMULATED_CAPACITY, _KICKOFF)
        assert result["can_accommodate"] is True

    def test_group_over_capacity_cannot_accommodate(self):
        result = check_bar_availability("Any Bar", _SIMULATED_CAPACITY + 1, _KICKOFF)
        assert result["status"] == "success"
        assert result["can_accommodate"] is False

    def test_over_capacity_includes_message(self):
        result = check_bar_availability("Any Bar", _SIMULATED_CAPACITY + 1, _KICKOFF)
        assert "message" in result
        assert len(result["message"]) > 0

    def test_available_seats_equals_simulated_capacity(self):
        result = check_bar_availability("Any Bar", 4, _KICKOFF)
        assert result["available_seats"] == _SIMULATED_CAPACITY

    def test_venue_name_is_echoed(self):
        result = check_bar_availability("The Kop End", 3, _KICKOFF)
        assert result["venue"] == "The Kop End"

    def test_party_size_is_echoed(self):
        result = check_bar_availability("Any Bar", 7, _KICKOFF)
        assert result["party_size"] == 7

    def test_match_time_is_echoed(self):
        result = check_bar_availability("Any Bar", 2, _KICKOFF)
        assert result["match_time"] == _KICKOFF

    def test_works_with_any_venue_name(self):
        result = check_bar_availability("A Real Google Maps Bar", 5, _KICKOFF)
        assert result["status"] == "success"

"""Tests for tools/get_travel_route.py.

This tool is pure logic with no external calls — no mocking required.
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_concierge.tools.get_travel_route import get_travel_route

_KICKOFF = "2026-03-14T17:30:00Z"


class TestGetTravelRoute:
    def test_valid_request_returns_success(self):
        result = get_travel_route("Pitch & Pint, London", _KICKOFF)
        assert result["status"] == "success"

    def test_destination_is_echoed(self):
        result = get_travel_route("The Kop End", _KICKOFF)
        assert result["destination"] == "The Kop End"

    def test_kickoff_time_is_echoed(self):
        result = get_travel_route("Pitch & Pint", _KICKOFF)
        assert result["kickoff_utc"] == _KICKOFF

    def test_all_routes_is_non_empty_list(self):
        result = get_travel_route("Pitch & Pint", _KICKOFF)
        assert isinstance(result["all_routes"], list)
        assert len(result["all_routes"]) > 0

    def test_each_route_has_required_fields(self):
        result = get_travel_route("Pitch & Pint", _KICKOFF)
        for route in result["all_routes"]:
            for f in ("mode", "duration_mins", "cost", "depart_by", "arrive_by"):
                assert f in route, f"Route missing field '{f}': {route}"

    def test_recommended_route_is_present(self):
        result = get_travel_route("Pitch & Pint", _KICKOFF)
        assert "recommended_route" in result
        assert result["recommended_route"] is not None

    def test_recommended_route_has_mode(self):
        result = get_travel_route("Pitch & Pint", _KICKOFF)
        assert "mode" in result["recommended_route"]

    def test_invalid_kickoff_format_returns_error(self):
        result = get_travel_route("Pitch & Pint", "not-a-date")
        assert result["status"] == "error"

    def test_target_arrival_is_30_mins_before_kickoff(self):
        result = get_travel_route("Pitch & Pint", _KICKOFF)
        kickoff = datetime.datetime.fromisoformat(_KICKOFF.replace("Z", "+00:00"))
        target = datetime.datetime.fromisoformat(result["target_arrival_utc"])
        assert (kickoff - target).total_seconds() == 30 * 60

    def test_tip_key_is_present(self):
        result = get_travel_route("Pitch & Pint", _KICKOFF)
        assert "tip" in result

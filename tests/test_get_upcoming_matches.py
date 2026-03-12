"""Tests for tools/get_upcoming_matches.py.

All calls to football_data_get are mocked — no live network requests.
"""

import datetime as dt
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from event_concierge.tools.get_upcoming_matches import get_upcoming_matches
from helpers import MOCK_API_EMPTY

_PATCH = "event_concierge.tools.get_upcoming_matches.football_data_get"


def _future_payload(hours_offset: float = 2.0) -> dict:
    """Build a football-data.org response with one match *hours_offset* hours ahead."""
    kickoff = (
        dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours_offset)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "matches": [{
            "id": 77777,
            "utcDate": kickoff,
            "status": "TIMED",
            "venue": "Emirates Stadium, London",
            "homeTeam": {"id": 57, "name": "Arsenal"},
            "awayTeam": {"id": 73, "name": "Tottenham Hotspur"},
            "competition": {"id": 2021, "name": "Premier League"},
        }],
        "resultSet": {"count": 1},
        "filters": {},
    }


class TestGetUpcomingMatches:
    def test_returns_success(self):
        with patch(_PATCH, return_value=_future_payload()):
            result = get_upcoming_matches(hours_ahead=24)
        assert result["status"] == "success"

    def test_contains_required_keys(self):
        with patch(_PATCH, return_value=_future_payload()):
            result = get_upcoming_matches()
        for key in ("window_hours", "from_utc", "to_utc",
                    "total_matches", "matches", "summary"):
            assert key in result, f"Missing key: {key}"

    def test_default_window_is_24_hours(self):
        with patch(_PATCH, return_value=_future_payload()):
            result = get_upcoming_matches()
        assert result["window_hours"] == 24

    def test_custom_window_is_respected(self):
        with patch(_PATCH, return_value=_future_payload()):
            result = get_upcoming_matches(hours_ahead=48)
        assert result["window_hours"] == 48

    def test_match_inside_window_is_included(self):
        with patch(_PATCH, return_value=_future_payload(hours_offset=2)):
            result = get_upcoming_matches(hours_ahead=24)
        assert result["total_matches"] >= 1

    def test_match_outside_window_is_excluded(self):
        with patch(_PATCH, return_value=_future_payload(hours_offset=30)):
            result = get_upcoming_matches(hours_ahead=24)
        assert result["total_matches"] == 0

    def test_each_match_has_required_fields(self):
        with patch(_PATCH, return_value=_future_payload()):
            result = get_upcoming_matches(hours_ahead=24)
        for m in result["matches"]:
            for f in ("home", "away", "kickoff_utc", "kickoff_formatted",
                      "competition", "venue", "location_hint"):
                assert f in m, f"Match missing field '{f}': {m}"

    def test_location_hint_equals_venue_when_venue_is_known(self):
        with patch(_PATCH, return_value=_future_payload()):
            result = get_upcoming_matches(hours_ahead=24)
        match = result["matches"][0]
        assert match["location_hint"] == "Emirates Stadium, London"

    def test_location_hint_falls_back_to_home_team_when_venue_tbc(self):
        kickoff = (
            dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = {
            "matches": [{
                "id": 55555,
                "utcDate": kickoff,
                "status": "TIMED",
                "venue": None,
                "homeTeam": {"id": 61, "name": "Chelsea FC"},
                "awayTeam": {"id": 65, "name": "Manchester City"},
                "competition": {"id": 2021, "name": "Premier League"},
            }],
            "resultSet": {"count": 1},
            "filters": {},
        }
        with patch(_PATCH, return_value=payload):
            result = get_upcoming_matches(hours_ahead=24)
        match = result["matches"][0]
        assert match["venue"] == "Venue TBC"
        assert match["location_hint"] == "Chelsea FC"

    def test_location_hint_is_never_venue_tbc_string(self):
        kickoff = (
            dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=2)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = {
            "matches": [{
                "id": 55556,
                "utcDate": kickoff,
                "status": "TIMED",
                "venue": None,
                "homeTeam": {"id": 61, "name": "Chelsea FC"},
                "awayTeam": {"id": 65, "name": "Manchester City"},
                "competition": {"id": 2021, "name": "Premier League"},
            }],
            "resultSet": {"count": 1},
            "filters": {},
        }
        with patch(_PATCH, return_value=payload):
            result = get_upcoming_matches(hours_ahead=24)
        assert result["matches"][0]["location_hint"] != "Venue TBC"

    def test_matches_are_sorted_by_kickoff(self):
        k1 = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        k2 = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=3)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        payload = {
            "matches": [
                {"id": 1, "utcDate": k2, "status": "TIMED", "venue": "",
                 "homeTeam": {"name": "A"}, "awayTeam": {"name": "B"},
                 "competition": {"name": "Premier League"}},
                {"id": 2, "utcDate": k1, "status": "TIMED", "venue": "",
                 "homeTeam": {"name": "C"}, "awayTeam": {"name": "D"},
                 "competition": {"name": "Premier League"}},
            ],
            "resultSet": {"count": 2},
            "filters": {},
        }
        with patch(_PATCH, return_value=payload):
            result = get_upcoming_matches(hours_ahead=24)
        kickoffs = [m["kickoff_utc"] for m in result["matches"]]
        assert kickoffs == sorted(kickoffs)

    def test_no_matches_returns_success_with_empty_list(self):
        with patch(_PATCH, return_value=MOCK_API_EMPTY):
            result = get_upcoming_matches(hours_ahead=24)
        assert result["status"] == "success"
        assert result["total_matches"] == 0
        assert result["matches"] == []

    def test_api_exception_returns_error(self):
        with patch(_PATCH, side_effect=Exception("network error")):
            result = get_upcoming_matches()
        assert result["status"] == "error"
        assert "network error" in result["error_message"]

    def test_summary_mentions_match_count(self):
        with patch(_PATCH, return_value=_future_payload()):
            result = get_upcoming_matches(hours_ahead=24)
        assert str(result["total_matches"]) in result["summary"]

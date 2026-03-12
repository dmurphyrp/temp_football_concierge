"""Tests for tools/get_next_match.py.

All calls to football_data_get are mocked — no live network requests.
"""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from event_concierge.tools.get_next_match import get_next_match
from helpers import MOCK_API_RESPONSE, MOCK_API_EMPTY, MOCK_API_VENUE_TBC

_PATCH = "event_concierge.tools.get_next_match.football_data_get"


class TestGetNextMatch:
    def test_known_team_returns_success(self):
        with patch(_PATCH, return_value=MOCK_API_RESPONSE):
            result = get_next_match("Arsenal")
        assert result["status"] == "success"

    def test_team_name_taken_from_fixture(self):
        with patch(_PATCH, return_value=MOCK_API_RESPONSE):
            result = get_next_match("Arsenal")
        assert result["team"] == "Arsenal"

    def test_opponent_is_populated(self):
        with patch(_PATCH, return_value=MOCK_API_RESPONSE):
            result = get_next_match("Arsenal")
        assert result["opponent"] == "Tottenham Hotspur"

    def test_kickoff_utc_is_normalised(self):
        with patch(_PATCH, return_value=MOCK_API_RESPONSE):
            result = get_next_match("Arsenal")
        assert result["kickoff_utc"] == "2026-03-14T17:30:00Z"

    def test_kickoff_formatted_is_human_readable(self):
        with patch(_PATCH, return_value=MOCK_API_RESPONSE):
            result = get_next_match("Arsenal")
        assert "2026" in result["kickoff_formatted"]
        assert "UTC" in result["kickoff_formatted"]

    def test_home_game_flag_true_for_home_side(self):
        with patch(_PATCH, return_value=MOCK_API_RESPONSE):
            result = get_next_match("Arsenal")
        assert result["home_game"] is True

    def test_home_game_flag_false_for_away_side(self):
        with patch(_PATCH, return_value=MOCK_API_RESPONSE):
            result = get_next_match("Tottenham Hotspur")
        assert result["home_game"] is False

    def test_contains_required_fields(self):
        with patch(_PATCH, return_value=MOCK_API_RESPONSE):
            result = get_next_match("Arsenal")
        for field in ("team", "opponent", "home_team", "kickoff_utc",
                      "kickoff_formatted", "venue", "location_hint",
                      "competition", "home_game", "broadcast"):
            assert field in result, f"Missing field: {field}"

    def test_competition_is_populated(self):
        with patch(_PATCH, return_value=MOCK_API_RESPONSE):
            result = get_next_match("Arsenal")
        assert result["competition"] == "Premier League"

    def test_venue_is_populated(self):
        with patch(_PATCH, return_value=MOCK_API_RESPONSE):
            result = get_next_match("Arsenal")
        assert result["venue"] == "Emirates Stadium, London"

    def test_home_team_is_always_home_side(self):
        with patch(_PATCH, return_value=MOCK_API_RESPONSE):
            result = get_next_match("Tottenham Hotspur")
        assert result["home_team"] == "Arsenal"

    def test_location_hint_equals_venue_when_venue_is_known(self):
        with patch(_PATCH, return_value=MOCK_API_RESPONSE):
            result = get_next_match("Arsenal")
        assert result["location_hint"] == "Emirates Stadium, London"

    def test_location_hint_falls_back_to_home_team_when_venue_tbc(self):
        with patch(_PATCH, return_value=MOCK_API_VENUE_TBC):
            result = get_next_match("Arsenal")
        assert result["venue"] == "Venue TBC"
        assert result["location_hint"] == "Everton FC"

    def test_location_hint_is_never_venue_tbc_string(self):
        with patch(_PATCH, return_value=MOCK_API_VENUE_TBC):
            result = get_next_match("Arsenal")
        assert result["location_hint"] != "Venue TBC"

    def test_team_not_found_returns_error(self):
        with patch(_PATCH, return_value=MOCK_API_EMPTY):
            result = get_next_match("Hogwarts FC")
        assert result["status"] == "error"
        assert "error_message" in result

    def test_empty_fixtures_returns_error(self):
        with patch(_PATCH, return_value=MOCK_API_EMPTY):
            result = get_next_match("Arsenal")
        assert result["status"] == "error"

    def test_api_exception_returns_error(self):
        with patch(_PATCH, side_effect=Exception("network timeout")):
            result = get_next_match("Arsenal")
        assert result["status"] == "error"
        assert "network timeout" in result["error_message"]

    def test_earliest_match_is_returned(self):
        payload = {
            "matches": [
                {"id": 201, "utcDate": "2026-03-21T15:00:00Z", "status": "TIMED",
                 "venue": "Emirates", "homeTeam": {"name": "Arsenal"},
                 "awayTeam": {"name": "Later Opponent"},
                 "competition": {"name": "Premier League"}},
                {"id": 200, "utcDate": "2026-03-14T15:00:00Z", "status": "TIMED",
                 "venue": "Emirates", "homeTeam": {"name": "Arsenal"},
                 "awayTeam": {"name": "First Opponent"},
                 "competition": {"name": "Premier League"}},
            ],
            "resultSet": {"count": 2},
            "filters": {},
        }
        with patch(_PATCH, return_value=payload):
            result = get_next_match("Arsenal")
        assert result["status"] == "success"
        assert result["opponent"] == "First Opponent"

    def test_short_name_alias_man_utd(self):
        payload = {
            "matches": [{
                "id": 200, "utcDate": "2026-03-21T12:30:00Z", "status": "TIMED",
                "venue": "Old Trafford",
                "homeTeam": {"id": 66, "name": "Manchester United"},
                "awayTeam": {"id": 57, "name": "Arsenal"},
                "competition": {"id": 2021, "name": "Premier League"},
            }],
            "resultSet": {"count": 1},
            "filters": {},
        }
        with patch(_PATCH, return_value=payload):
            result = get_next_match("Man Utd")
        assert result["status"] == "success"
        assert result["team"] == "Manchester United"

    def test_correct_team_selected_from_many_fixtures(self):
        payload = {
            "matches": [
                {"id": 300, "utcDate": "2026-03-14T12:30:00Z", "status": "TIMED",
                 "venue": "Anfield", "homeTeam": {"name": "Liverpool FC"},
                 "awayTeam": {"name": "Everton FC"},
                 "competition": {"name": "Premier League"}},
                {"id": 301, "utcDate": "2026-03-14T15:00:00Z", "status": "TIMED",
                 "venue": "Emirates", "homeTeam": {"name": "Arsenal"},
                 "awayTeam": {"name": "Chelsea FC"},
                 "competition": {"name": "Premier League"}},
            ],
            "resultSet": {"count": 2},
            "filters": {},
        }
        with patch(_PATCH, return_value=payload):
            result = get_next_match("Arsenal")
        assert result["status"] == "success"
        assert result["opponent"] == "Chelsea FC"

"""
Unit tests for the Matchday Concierge agent tools.

External API calls (MobFot, Google Maps) are fully mocked so the suite
runs without network access or real credentials.

Tests cover:
  - get_upcoming_matches  (mocked MobFot)
  - get_next_match        (mocked MobFot)
  - find_football_bars    (mocked googlemaps.Client)
  - check_bar_availability
  - book_table
  - notify_friends
  - get_travel_route
  - add_to_calendar
  - root_agent configuration
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multi_tool_agent.agent import (
    _SIMULATED_CAPACITY,
    add_to_calendar,
    book_table,
    check_bar_availability,
    find_football_bars,
    get_next_match,
    get_travel_route,
    get_upcoming_matches,
    notify_friends,
    root_agent,
)


# ---------------------------------------------------------------------------
# Shared mock payloads
# ---------------------------------------------------------------------------
_MOCK_MATCHES_BY_DATE = {
    "leagues": [
        {
            "id": 47,
            "name": "Premier League",
            "matches": [
                {
                    "id": 12345,
                    "home": {"id": 9825, "name": "Arsenal"},
                    "away": {"id": 8586, "name": "Tottenham Hotspur"},
                    "status": {
                        "utcTime": "2026-03-14T17:30:00.000Z",
                        "finished": False,
                        "started": False,
                        "cancelled": False,
                    },
                    "venue": "Emirates Stadium, London",
                }
            ],
        }
    ]
}

_MOCK_MATCHES_EMPTY = {"leagues": []}

_MOCK_GEOCODE = [
    {"geometry": {"location": {"lat": 51.5074, "lng": -0.1278}}}
]

_MOCK_PLACES = {
    "status": "OK",
    "results": [
        {
            "place_id": "ChIJtest001",
            "name": "Pitch & Pint",
            "vicinity": "200 Stadium Road, London",
            "rating": 4.8,
            "user_ratings_total": 320,
            "opening_hours": {"open_now": True},
            "business_status": "OPERATIONAL",
            "geometry": {"location": {"lat": 51.508, "lng": -0.128}},
            "price_level": 2,
        },
        {
            "place_id": "ChIJtest002",
            "name": "The Anchor",
            "vicinity": "5 Riverside Walk, London",
            "rating": 4.5,
            "user_ratings_total": 180,
            "opening_hours": {"open_now": True},
            "business_status": "OPERATIONAL",
            "geometry": {"location": {"lat": 51.509, "lng": -0.129}},
            "price_level": 1,
        },
    ],
}


def _make_fotmob_mock(matches_data=None, empty_days: int = 0):
    """Returns a patched MobFot class whose instance returns the given data.

    Args:
        matches_data: The payload get_matches_by_date returns once a match is found.
        empty_days: How many days of empty results precede the match day.
    """
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_cls.return_value = mock_instance
    call_count = [0]

    def _side_effect(date_str, time_zone="America/New_York"):
        call_count[0] += 1
        if call_count[0] <= empty_days:
            return _MOCK_MATCHES_EMPTY
        return matches_data if matches_data is not None else _MOCK_MATCHES_BY_DATE

    mock_instance.get_matches_by_date.side_effect = _side_effect
    return mock_cls


def _make_gmaps_mock(geocode_data=None, places_data=None):
    """Returns a patched googlemaps.Client class with preset return values."""
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_cls.return_value = mock_instance
    mock_instance.geocode.return_value = _MOCK_GEOCODE if geocode_data is None else geocode_data
    mock_instance.places_nearby.return_value = _MOCK_PLACES if places_data is None else places_data
    return mock_cls


# ===========================================================================
# get_upcoming_matches
# ===========================================================================
class TestGetUpcomingMatches:
    # Build a payload where kickoff is 2 hours from now so it always falls
    # inside any reasonable hours_ahead window during test execution.
    @staticmethod
    def _make_future_payload(hours_offset: float = 2.0) -> dict:
        import datetime as dt
        kickoff = (
            dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=hours_offset)
        ).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        return {
            "leagues": [{
                "id": 47,
                "name": "Premier League",
                "matches": [{
                    "id": 77777,
                    "home": {"id": 9825, "name": "Arsenal"},
                    "away": {"id": 8586, "name": "Tottenham Hotspur"},
                    "status": {"utcTime": kickoff, "finished": False, "started": False},
                    "venue": "Emirates Stadium, London",
                }],
            }]
        }

    def test_returns_success(self):
        with patch("multi_tool_agent.agent.MobFot",
                   _make_fotmob_mock(matches_data=self._make_future_payload())):
            result = get_upcoming_matches(hours_ahead=24)
        assert result["status"] == "success"

    def test_contains_required_keys(self):
        with patch("multi_tool_agent.agent.MobFot",
                   _make_fotmob_mock(matches_data=self._make_future_payload())):
            result = get_upcoming_matches()
        for key in ("window_hours", "from_utc", "to_utc",
                    "total_matches", "matches", "summary"):
            assert key in result, f"Missing key: {key}"

    def test_default_window_is_24_hours(self):
        with patch("multi_tool_agent.agent.MobFot",
                   _make_fotmob_mock(matches_data=self._make_future_payload())):
            result = get_upcoming_matches()
        assert result["window_hours"] == 24

    def test_custom_window_is_respected(self):
        with patch("multi_tool_agent.agent.MobFot",
                   _make_fotmob_mock(matches_data=self._make_future_payload())):
            result = get_upcoming_matches(hours_ahead=48)
        assert result["window_hours"] == 48

    def test_match_in_window_is_included(self):
        with patch("multi_tool_agent.agent.MobFot",
                   _make_fotmob_mock(matches_data=self._make_future_payload(hours_offset=2))):
            result = get_upcoming_matches(hours_ahead=24)
        assert result["total_matches"] >= 1

    def test_match_outside_window_is_excluded(self):
        # Kickoff 30 hours away, but we only look 24 hours ahead
        with patch("multi_tool_agent.agent.MobFot",
                   _make_fotmob_mock(matches_data=self._make_future_payload(hours_offset=30))):
            result = get_upcoming_matches(hours_ahead=24)
        assert result["total_matches"] == 0

    def test_each_match_has_required_fields(self):
        with patch("multi_tool_agent.agent.MobFot",
                   _make_fotmob_mock(matches_data=self._make_future_payload())):
            result = get_upcoming_matches(hours_ahead=24)
        for m in result["matches"]:
            for f in ("home", "away", "kickoff_utc", "kickoff_formatted",
                      "competition", "venue"):
                assert f in m, f"Match missing field '{f}': {m}"

    def test_matches_are_sorted_by_kickoff(self):
        import datetime as dt
        k1 = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        k2 = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=3)).strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        two_match_payload = {
            "leagues": [{
                "id": 47, "name": "Premier League",
                "matches": [
                    {"id": 1, "home": {"name": "A"}, "away": {"name": "B"},
                     "status": {"utcTime": k2, "finished": False, "started": False},
                     "venue": ""},
                    {"id": 2, "home": {"name": "C"}, "away": {"name": "D"},
                     "status": {"utcTime": k1, "finished": False, "started": False},
                     "venue": ""},
                ],
            }]
        }
        with patch("multi_tool_agent.agent.MobFot",
                   _make_fotmob_mock(matches_data=two_match_payload)):
            result = get_upcoming_matches(hours_ahead=24)
        kickoffs = [m["kickoff_utc"] for m in result["matches"]]
        assert kickoffs == sorted(kickoffs)

    def test_no_matches_returns_success_with_empty_list(self):
        with patch("multi_tool_agent.agent.MobFot",
                   _make_fotmob_mock(matches_data=_MOCK_MATCHES_EMPTY)):
            result = get_upcoming_matches(hours_ahead=24)
        assert result["status"] == "success"
        assert result["total_matches"] == 0
        assert result["matches"] == []

    def test_finished_matches_are_excluded(self):
        import datetime as dt
        past_kickoff = (
            dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)
        ).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        finished_payload = {
            "leagues": [{
                "id": 47, "name": "Premier League",
                "matches": [{
                    "id": 55,
                    "home": {"name": "X"}, "away": {"name": "Y"},
                    "status": {"utcTime": past_kickoff,
                               "finished": True, "started": True},
                    "venue": "",
                }],
            }]
        }
        with patch("multi_tool_agent.agent.MobFot",
                   _make_fotmob_mock(matches_data=finished_payload)):
            result = get_upcoming_matches(hours_ahead=24)
        assert result["total_matches"] == 0

    def test_api_exception_returns_error(self):
        mock_cls = MagicMock()
        mock_cls.side_effect = Exception("network error")
        with patch("multi_tool_agent.agent.MobFot", mock_cls):
            result = get_upcoming_matches()
        assert result["status"] == "error"
        assert "network error" in result["error_message"]

    def test_summary_mentions_match_count(self):
        with patch("multi_tool_agent.agent.MobFot",
                   _make_fotmob_mock(matches_data=self._make_future_payload())):
            result = get_upcoming_matches(hours_ahead=24)
        assert str(result["total_matches"]) in result["summary"]


# ===========================================================================
# get_next_match
# ===========================================================================
class TestGetNextMatch:
    def test_known_team_returns_success(self):
        with patch("multi_tool_agent.agent.MobFot", _make_fotmob_mock()):
            result = get_next_match("Arsenal")
        assert result["status"] == "success"

    def test_team_name_taken_from_fixture(self):
        with patch("multi_tool_agent.agent.MobFot", _make_fotmob_mock()):
            result = get_next_match("Arsenal")
        assert result["team"] == "Arsenal"

    def test_opponent_is_populated(self):
        with patch("multi_tool_agent.agent.MobFot", _make_fotmob_mock()):
            result = get_next_match("Arsenal")
        assert result["opponent"] == "Tottenham Hotspur"

    def test_kickoff_utc_is_normalised(self):
        with patch("multi_tool_agent.agent.MobFot", _make_fotmob_mock()):
            result = get_next_match("Arsenal")
        # FotMob returns milliseconds (.000Z); we normalise to no-millis ISO
        assert result["kickoff_utc"] == "2026-03-14T17:30:00Z"

    def test_kickoff_formatted_is_human_readable(self):
        with patch("multi_tool_agent.agent.MobFot", _make_fotmob_mock()):
            result = get_next_match("Arsenal")
        assert "2026" in result["kickoff_formatted"]
        assert "UTC" in result["kickoff_formatted"]

    def test_home_game_flag_is_true_for_home_side(self):
        with patch("multi_tool_agent.agent.MobFot", _make_fotmob_mock()):
            result = get_next_match("Arsenal")
        assert result["home_game"] is True

    def test_home_game_flag_is_false_for_away_side(self):
        with patch("multi_tool_agent.agent.MobFot", _make_fotmob_mock()):
            result = get_next_match("Tottenham Hotspur")
        assert result["home_game"] is False

    def test_contains_required_fields(self):
        with patch("multi_tool_agent.agent.MobFot", _make_fotmob_mock()):
            result = get_next_match("Arsenal")
        for field in ("team", "opponent", "kickoff_utc", "kickoff_formatted",
                      "venue", "competition", "home_game", "broadcast"):
            assert field in result, f"Missing field: {field}"

    def test_competition_is_populated(self):
        with patch("multi_tool_agent.agent.MobFot", _make_fotmob_mock()):
            result = get_next_match("Arsenal")
        assert result["competition"] == "Premier League"

    def test_team_not_in_any_fixture_returns_error(self):
        with patch("multi_tool_agent.agent.MobFot", _make_fotmob_mock(matches_data=_MOCK_MATCHES_EMPTY)):
            result = get_next_match("Hogwarts FC")
        assert result["status"] == "error"
        assert "error_message" in result

    def test_only_finished_matches_returns_error(self):
        finished_data = {
            "leagues": [{
                "id": 47,
                "name": "Premier League",
                "matches": [{
                    "id": 99,
                    "home": {"id": 9825, "name": "Arsenal"},
                    "away": {"id": 1, "name": "Opponent"},
                    "status": {"utcTime": "2026-01-01T15:00:00Z",
                               "finished": True, "started": True},
                    "venue": "Emirates Stadium",
                }],
            }]
        }
        with patch("multi_tool_agent.agent.MobFot", _make_fotmob_mock(matches_data=finished_data)):
            result = get_next_match("Arsenal")
        assert result["status"] == "error"

    def test_api_exception_returns_error(self):
        mock_cls = MagicMock()
        mock_cls.side_effect = Exception("network timeout")
        with patch("multi_tool_agent.agent.MobFot", mock_cls):
            result = get_next_match("Arsenal")
        assert result["status"] == "error"
        assert "network timeout" in result["error_message"]

    def test_match_found_after_empty_days(self):
        # Simulates team playing 3 days from now
        with patch("multi_tool_agent.agent.MobFot", _make_fotmob_mock(empty_days=3)):
            result = get_next_match("Arsenal")
        assert result["status"] == "success"

    def test_short_name_alias_man_utd(self):
        utd_data = {
            "leagues": [{
                "id": 47,
                "name": "Premier League",
                "matches": [{
                    "id": 200,
                    "home": {"id": 10260, "name": "Manchester United"},
                    "away": {"id": 9825, "name": "Arsenal"},
                    "status": {"utcTime": "2026-03-21T12:30:00.000Z",
                               "finished": False, "started": False},
                    "venue": "Old Trafford",
                }],
            }]
        }
        with patch("multi_tool_agent.agent.MobFot", _make_fotmob_mock(matches_data=utd_data)):
            result = get_next_match("Man Utd")
        assert result["status"] == "success"
        assert result["team"] == "Manchester United"

    def test_started_matches_are_skipped(self):
        started_then_upcoming = {
            "leagues": [{
                "id": 47,
                "name": "Premier League",
                "matches": [
                    {
                        "id": 100,
                        "home": {"id": 9825, "name": "Arsenal"},
                        "away": {"id": 1, "name": "In Progress FC"},
                        "status": {"utcTime": "2026-03-14T15:00:00.000Z",
                                   "finished": False, "started": True},
                        "venue": "Emirates",
                    },
                    {
                        "id": 101,
                        "home": {"id": 9825, "name": "Arsenal"},
                        "away": {"id": 2, "name": "Next Opponent"},
                        "status": {"utcTime": "2026-03-21T15:00:00.000Z",
                                   "finished": False, "started": False},
                        "venue": "Emirates",
                    },
                ],
            }]
        }
        with patch("multi_tool_agent.agent.MobFot", _make_fotmob_mock(matches_data=started_then_upcoming)):
            result = get_next_match("Arsenal")
        assert result["status"] == "success"
        assert result["opponent"] == "Next Opponent"


# ===========================================================================
# find_football_bars
# ===========================================================================
class TestFindFootballBars:
    def test_returns_success(self):
        with (patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test_key"}),
              patch("multi_tool_agent.agent.googlemaps.Client", _make_gmaps_mock())):
            result = find_football_bars("London Bridge")
        assert result["status"] == "success"

    def test_contains_required_keys(self):
        with (patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test_key"}),
              patch("multi_tool_agent.agent.googlemaps.Client", _make_gmaps_mock())):
            result = find_football_bars("Shoreditch")
        for key in ("location_searched", "radius_km", "venues_found", "venues", "summary"):
            assert key in result, f"Missing key: {key}"

    def test_location_is_echoed(self):
        with (patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test_key"}),
              patch("multi_tool_agent.agent.googlemaps.Client", _make_gmaps_mock())):
            result = find_football_bars("Canary Wharf")
        assert result["location_searched"] == "Canary Wharf"

    def test_default_radius_is_5(self):
        with (patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test_key"}),
              patch("multi_tool_agent.agent.googlemaps.Client", _make_gmaps_mock())):
            result = find_football_bars("Oxford Street")
        assert result["radius_km"] == 5

    def test_custom_radius_is_respected(self):
        with (patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test_key"}),
              patch("multi_tool_agent.agent.googlemaps.Client", _make_gmaps_mock())):
            result = find_football_bars("Old Street", radius_km=10)
        assert result["radius_km"] == 10

    def test_venues_sorted_by_rating_descending(self):
        with (patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test_key"}),
              patch("multi_tool_agent.agent.googlemaps.Client", _make_gmaps_mock())):
            result = find_football_bars("London")
        ratings = [v["rating"] or 0 for v in result["venues"]]
        assert ratings == sorted(ratings, reverse=True)

    def test_venues_count_matches_results(self):
        with (patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test_key"}),
              patch("multi_tool_agent.agent.googlemaps.Client", _make_gmaps_mock())):
            result = find_football_bars("London")
        assert result["venues_found"] == len(result["venues"])

    def test_each_venue_has_required_fields(self):
        required = ("venue_id", "name", "address", "rating",
                    "user_ratings_total", "open_now", "business_status",
                    "price_level", "maps_url")
        with (patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test_key"}),
              patch("multi_tool_agent.agent.googlemaps.Client", _make_gmaps_mock())):
            result = find_football_bars("London")
        for v in result["venues"]:
            for f in required:
                assert f in v, f"Venue missing field '{f}': {v}"

    def test_maps_url_is_google_maps_link(self):
        with (patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test_key"}),
              patch("multi_tool_agent.agent.googlemaps.Client", _make_gmaps_mock())):
            result = find_football_bars("London")
        for v in result["venues"]:
            assert "google.com/maps" in v["maps_url"]

    def test_summary_mentions_radius(self):
        with (patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test_key"}),
              patch("multi_tool_agent.agent.googlemaps.Client", _make_gmaps_mock())):
            result = find_football_bars("London", radius_km=3)
        assert "3km" in result["summary"]

    def test_missing_api_key_returns_error(self):
        env_without_key = {k: v for k, v in os.environ.items()
                           if k != "GOOGLE_MAPS_API_KEY"}
        with patch.dict(os.environ, env_without_key, clear=True):
            result = find_football_bars("London")
        assert result["status"] == "error"
        assert "GOOGLE_MAPS_API_KEY" in result["error_message"]

    def test_bad_geocode_returns_error(self):
        with (patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test_key"}),
              patch("multi_tool_agent.agent.googlemaps.Client",
                    _make_gmaps_mock(geocode_data=[]))):
            result = find_football_bars("NonexistentPlace123")
        assert result["status"] == "error"

    def test_places_api_error_status_returns_error(self):
        bad_places = {"status": "REQUEST_DENIED", "results": []}
        with (patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test_key"}),
              patch("multi_tool_agent.agent.googlemaps.Client",
                    _make_gmaps_mock(places_data=bad_places))):
            result = find_football_bars("London")
        assert result["status"] == "error"

    def test_zero_results_returns_success_with_empty_list(self):
        zero_places = {"status": "ZERO_RESULTS", "results": []}
        with (patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test_key"}),
              patch("multi_tool_agent.agent.googlemaps.Client",
                    _make_gmaps_mock(places_data=zero_places))):
            result = find_football_bars("Remote Island")
        assert result["status"] == "success"
        assert result["venues"] == []

    def test_gmaps_exception_returns_error(self):
        mock_cls = MagicMock()
        mock_cls.side_effect = Exception("connection refused")
        with (patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test_key"}),
              patch("multi_tool_agent.agent.googlemaps.Client", mock_cls)):
            result = find_football_bars("London")
        assert result["status"] == "error"


# ===========================================================================
# check_bar_availability
# ===========================================================================
class TestCheckBarAvailability:
    KICKOFF = "2026-03-14T17:30:00Z"

    def test_small_group_can_accommodate(self):
        result = check_bar_availability("Pitch & Pint", 4, self.KICKOFF)
        assert result["status"] == "success"
        assert result["can_accommodate"] is True

    def test_group_at_capacity_can_accommodate(self):
        result = check_bar_availability("The Anchor", _SIMULATED_CAPACITY, self.KICKOFF)
        assert result["can_accommodate"] is True

    def test_group_over_capacity_cannot_accommodate(self):
        result = check_bar_availability("Any Bar", _SIMULATED_CAPACITY + 1, self.KICKOFF)
        assert result["status"] == "success"
        assert result["can_accommodate"] is False

    def test_over_capacity_includes_message(self):
        result = check_bar_availability("Any Bar", _SIMULATED_CAPACITY + 1, self.KICKOFF)
        assert "message" in result
        assert len(result["message"]) > 0

    def test_available_seats_equals_simulated_capacity(self):
        result = check_bar_availability("Any Bar", 4, self.KICKOFF)
        assert result["available_seats"] == _SIMULATED_CAPACITY

    def test_venue_name_is_echoed(self):
        result = check_bar_availability("The Kop End", 3, self.KICKOFF)
        assert result["venue"] == "The Kop End"

    def test_party_size_is_echoed(self):
        result = check_bar_availability("Any Bar", 7, self.KICKOFF)
        assert result["party_size"] == 7

    def test_match_time_is_echoed(self):
        result = check_bar_availability("Any Bar", 2, self.KICKOFF)
        assert result["match_time"] == self.KICKOFF

    def test_works_with_any_venue_name(self):
        result = check_bar_availability("A Real Google Maps Bar", 5, self.KICKOFF)
        assert result["status"] == "success"


# ===========================================================================
# book_table
# ===========================================================================
class TestBookTable:
    KICKOFF = "2026-03-14T17:30:00Z"

    def test_valid_booking_returns_success(self):
        result = book_table("Pitch & Pint", 4, self.KICKOFF)
        assert result["status"] == "success"

    def test_booking_reference_is_generated(self):
        result = book_table("Pitch & Pint", 2, self.KICKOFF)
        assert "booking_reference" in result
        assert result["booking_reference"].startswith("MC-")

    def test_booking_confirms_venue_name(self):
        result = book_table("The Anchor", 3, self.KICKOFF)
        assert result["venue"] == "The Anchor"

    def test_booking_confirms_party_size(self):
        result = book_table("The Anchor", 6, self.KICKOFF)
        assert result["party_size"] == 6

    def test_booking_confirms_match_time(self):
        result = book_table("Any Bar", 4, self.KICKOFF)
        assert result["match_time"] == self.KICKOFF

    def test_booking_at_capacity_succeeds(self):
        result = book_table("Any Bar", _SIMULATED_CAPACITY, self.KICKOFF)
        assert result["status"] == "success"

    def test_party_over_capacity_fails(self):
        result = book_table("Any Bar", _SIMULATED_CAPACITY + 1, self.KICKOFF)
        assert result["status"] == "error"
        assert "error_message" in result

    def test_empty_venue_name_fails(self):
        result = book_table("", 4, self.KICKOFF)
        assert result["status"] == "error"

    def test_booking_reference_is_deterministic(self):
        r1 = book_table("Pitch & Pint", 4, self.KICKOFF)
        r2 = book_table("Pitch & Pint", 4, self.KICKOFF)
        assert r1["booking_reference"] == r2["booking_reference"]

    def test_different_venues_produce_different_references(self):
        r1 = book_table("Bar A", 2, self.KICKOFF)
        r2 = book_table("Bar B", 2, self.KICKOFF)
        assert r1["booking_reference"] != r2["booking_reference"]

    def test_works_with_any_venue_name(self):
        result = book_table("A Real Google Maps Bar", 5, self.KICKOFF)
        assert result["status"] == "success"


# ===========================================================================
# notify_friends
# ===========================================================================
class TestNotifyFriends:
    MSG = "Arsenal v Spurs at Pitch & Pint, 17:30 — who's in?"

    def test_whatsapp_notification_succeeds(self):
        result = notify_friends(self.MSG, platform="WhatsApp")
        assert result["status"] == "success"

    def test_telegram_notification_succeeds(self):
        result = notify_friends(self.MSG, platform="Telegram")
        assert result["status"] == "success"

    def test_sms_notification_succeeds(self):
        result = notify_friends(self.MSG, platform="SMS")
        assert result["status"] == "success"

    def test_unsupported_platform_returns_error(self):
        result = notify_friends(self.MSG, platform="Carrier Pigeon")
        assert result["status"] == "error"
        assert "error_message" in result

    def test_message_is_echoed(self):
        result = notify_friends(self.MSG)
        assert result["message_sent"] == self.MSG

    def test_custom_group_is_echoed(self):
        result = notify_friends(self.MSG, friend_group="Match Day Legends")
        assert result["group"] == "Match Day Legends"

    def test_default_group_is_friday_footy_crew(self):
        result = notify_friends(self.MSG)
        assert result["group"] == "Friday Footy Crew"

    def test_recipients_count_is_positive(self):
        result = notify_friends(self.MSG)
        assert result["recipients_count"] > 0

    def test_recipients_is_list(self):
        result = notify_friends(self.MSG)
        assert isinstance(result["recipients"], list)

    def test_confirmation_mentions_platform(self):
        result = notify_friends(self.MSG, platform="Telegram")
        assert "Telegram" in result["confirmation"]

    def test_confirmation_mentions_group(self):
        result = notify_friends(self.MSG, friend_group="Pub Squad")
        assert "Pub Squad" in result["confirmation"]


# ===========================================================================
# get_travel_route
# ===========================================================================
class TestGetTravelRoute:
    KICKOFF = "2026-03-14T17:30:00Z"

    def test_valid_request_returns_success(self):
        result = get_travel_route("Pitch & Pint, London", self.KICKOFF)
        assert result["status"] == "success"

    def test_destination_is_echoed(self):
        result = get_travel_route("The Kop End", self.KICKOFF)
        assert result["destination"] == "The Kop End"

    def test_kickoff_time_is_echoed(self):
        result = get_travel_route("Pitch & Pint", self.KICKOFF)
        assert result["kickoff_utc"] == self.KICKOFF

    def test_all_routes_is_non_empty_list(self):
        result = get_travel_route("Pitch & Pint", self.KICKOFF)
        assert isinstance(result["all_routes"], list)
        assert len(result["all_routes"]) > 0

    def test_each_route_has_required_fields(self):
        result = get_travel_route("Pitch & Pint", self.KICKOFF)
        for route in result["all_routes"]:
            for f in ("mode", "duration_mins", "cost", "depart_by", "arrive_by"):
                assert f in route, f"Route missing field '{f}': {route}"

    def test_recommended_route_is_present(self):
        result = get_travel_route("Pitch & Pint", self.KICKOFF)
        assert "recommended_route" in result
        assert result["recommended_route"] is not None

    def test_recommended_route_has_mode(self):
        result = get_travel_route("Pitch & Pint", self.KICKOFF)
        assert "mode" in result["recommended_route"]

    def test_invalid_kickoff_format_returns_error(self):
        result = get_travel_route("Pitch & Pint", "not-a-date")
        assert result["status"] == "error"

    def test_target_arrival_is_30_mins_before_kickoff(self):
        import datetime
        result = get_travel_route("Pitch & Pint", self.KICKOFF)
        kickoff = datetime.datetime.fromisoformat(self.KICKOFF.replace("Z", "+00:00"))
        target = datetime.datetime.fromisoformat(result["target_arrival_utc"])
        assert (kickoff - target).total_seconds() == 30 * 60

    def test_tip_key_is_present(self):
        result = get_travel_route("Pitch & Pint", self.KICKOFF)
        assert "tip" in result


# ===========================================================================
# add_to_calendar
# ===========================================================================
class TestAddToCalendar:
    TITLE = "Arsenal vs Spurs — Pitch & Pint"
    START = "2026-03-14T17:30:00Z"
    LOCATION = "12 Football Lane, London"

    def test_valid_event_returns_success(self):
        result = add_to_calendar(self.TITLE, self.START, self.LOCATION)
        assert result["status"] == "success"

    def test_event_id_is_generated(self):
        result = add_to_calendar(self.TITLE, self.START, self.LOCATION)
        assert "event_id" in result
        assert result["event_id"].startswith("CAL-")

    def test_event_title_is_echoed(self):
        result = add_to_calendar(self.TITLE, self.START, self.LOCATION)
        assert result["event_title"] == self.TITLE

    def test_location_is_echoed(self):
        result = add_to_calendar(self.TITLE, self.START, self.LOCATION)
        assert result["location"] == self.LOCATION

    def test_start_time_is_echoed(self):
        result = add_to_calendar(self.TITLE, self.START, self.LOCATION)
        assert result["start_utc"] == self.START

    def test_end_time_is_3_hours_after_start(self):
        import datetime
        result = add_to_calendar(self.TITLE, self.START, self.LOCATION)
        start = datetime.datetime.fromisoformat(self.START.replace("Z", "+00:00"))
        end = datetime.datetime.fromisoformat(
            result["end_utc"].replace("Z", "+00:00")
        )
        assert (end - start).total_seconds() == 3 * 3600

    def test_calendar_link_is_a_google_url(self):
        result = add_to_calendar(self.TITLE, self.START, self.LOCATION)
        assert result["calendar_link"].startswith("https://calendar.google.com")

    def test_calendar_link_contains_title(self):
        result = add_to_calendar(self.TITLE, self.START, self.LOCATION)
        assert "Arsenal" in result["calendar_link"]

    def test_description_is_included_when_provided(self):
        result = add_to_calendar(
            self.TITLE, self.START, self.LOCATION,
            description="Booking ref MC-00001. Liam, Seán attending."
        )
        assert "Booking ref" in result["description"]

    def test_description_defaults_to_empty_string(self):
        result = add_to_calendar(self.TITLE, self.START, self.LOCATION)
        assert result["description"] == ""

    def test_invalid_start_time_returns_error(self):
        result = add_to_calendar(self.TITLE, "not-a-date", self.LOCATION)
        assert result["status"] == "error"

    def test_event_id_is_deterministic(self):
        r1 = add_to_calendar(self.TITLE, self.START, self.LOCATION)
        r2 = add_to_calendar(self.TITLE, self.START, self.LOCATION)
        assert r1["event_id"] == r2["event_id"]

    def test_confirmation_message_is_present(self):
        result = add_to_calendar(self.TITLE, self.START, self.LOCATION)
        assert "confirmation" in result
        assert len(result["confirmation"]) > 0


# ===========================================================================
# root_agent configuration
# ===========================================================================
class TestRootAgentConfiguration:
    def test_agent_is_defined(self):
        assert root_agent is not None

    def test_agent_name(self):
        assert root_agent.name == "matchday_concierge"

    def test_agent_has_tools(self):
        assert hasattr(root_agent, "tools") or hasattr(root_agent, "_tools")

    def test_agent_model_is_gemini(self):
        assert "gemini" in root_agent.model.lower()

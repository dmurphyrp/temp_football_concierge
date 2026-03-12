"""Tests for tools/find_football_bars.py.

All calls to googlemaps.Client are mocked — no live network requests.
"""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from event_concierge.tools.find_football_bars import find_football_bars
from helpers import make_gmaps_mock

_PATCH = "event_concierge.tools.find_football_bars.googlemaps.Client"
_ENV = {"GOOGLE_MAPS_API_KEY": "test_key"}


class TestFindFootballBars:
    def test_returns_success(self):
        with patch.dict(os.environ, _ENV), patch(_PATCH, make_gmaps_mock()):
            result = find_football_bars("London Bridge")
        assert result["status"] == "success"

    def test_contains_required_keys(self):
        with patch.dict(os.environ, _ENV), patch(_PATCH, make_gmaps_mock()):
            result = find_football_bars("Shoreditch")
        for key in ("location_searched", "radius_km", "venues_found", "venues", "summary"):
            assert key in result, f"Missing key: {key}"

    def test_location_is_echoed(self):
        with patch.dict(os.environ, _ENV), patch(_PATCH, make_gmaps_mock()):
            result = find_football_bars("Canary Wharf")
        assert result["location_searched"] == "Canary Wharf"

    def test_default_radius_is_5(self):
        with patch.dict(os.environ, _ENV), patch(_PATCH, make_gmaps_mock()):
            result = find_football_bars("Oxford Street")
        assert result["radius_km"] == 5

    def test_custom_radius_is_respected(self):
        with patch.dict(os.environ, _ENV), patch(_PATCH, make_gmaps_mock()):
            result = find_football_bars("Old Street", radius_km=10)
        assert result["radius_km"] == 10

    def test_venues_sorted_by_rating_descending(self):
        with patch.dict(os.environ, _ENV), patch(_PATCH, make_gmaps_mock()):
            result = find_football_bars("London")
        ratings = [v["rating"] or 0 for v in result["venues"]]
        assert ratings == sorted(ratings, reverse=True)

    def test_venues_count_matches_results(self):
        with patch.dict(os.environ, _ENV), patch(_PATCH, make_gmaps_mock()):
            result = find_football_bars("London")
        assert result["venues_found"] == len(result["venues"])

    def test_each_venue_has_required_fields(self):
        required = ("venue_id", "name", "address", "rating",
                    "user_ratings_total", "open_now", "business_status",
                    "price_level", "maps_url")
        with patch.dict(os.environ, _ENV), patch(_PATCH, make_gmaps_mock()):
            result = find_football_bars("London")
        for v in result["venues"]:
            for f in required:
                assert f in v, f"Venue missing field '{f}': {v}"

    def test_maps_url_is_google_maps_link(self):
        with patch.dict(os.environ, _ENV), patch(_PATCH, make_gmaps_mock()):
            result = find_football_bars("London")
        for v in result["venues"]:
            assert "google.com/maps" in v["maps_url"]

    def test_summary_mentions_radius(self):
        with patch.dict(os.environ, _ENV), patch(_PATCH, make_gmaps_mock()):
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
        with patch.dict(os.environ, _ENV), patch(_PATCH, make_gmaps_mock(geocode_data=[])):
            result = find_football_bars("NonexistentPlace123")
        assert result["status"] == "error"

    def test_places_api_error_status_returns_error(self):
        bad_places = {"status": "REQUEST_DENIED", "results": []}
        with patch.dict(os.environ, _ENV), patch(_PATCH, make_gmaps_mock(places_data=bad_places)):
            result = find_football_bars("London")
        assert result["status"] == "error"

    def test_zero_results_returns_success_with_empty_list(self):
        zero_places = {"status": "ZERO_RESULTS", "results": []}
        with patch.dict(os.environ, _ENV), patch(_PATCH, make_gmaps_mock(places_data=zero_places)):
            result = find_football_bars("Remote Island")
        assert result["status"] == "success"
        assert result["venues"] == []

    def test_gmaps_exception_returns_error(self):
        from unittest.mock import MagicMock
        mock_cls = MagicMock()
        mock_cls.side_effect = Exception("connection refused")
        with patch.dict(os.environ, _ENV), patch(_PATCH, mock_cls):
            result = find_football_bars("London")
        assert result["status"] == "error"

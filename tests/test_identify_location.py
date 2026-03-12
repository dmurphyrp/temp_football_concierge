"""Tests for tools/identify_location.py.

All calls to googlemaps.Client are mocked — no live network requests.
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_concierge.tools.identify_location import identify_location

_PATCH = "event_concierge.tools.identify_location.googlemaps.Client"
_ENV = {"GOOGLE_MAPS_API_KEY": "test_key"}

_MOCK_GEOCODE_RESULT = [
    {
        "formatted_address": "Goodison Park, Goodison Rd, Liverpool L4 4EL, UK",
        "geometry": {"location": {"lat": 53.4388, "lng": -2.9661}},
        "address_components": [
            {"long_name": "Liverpool", "types": ["locality", "political"]},
            {"long_name": "Merseyside", "types": ["administrative_area_level_2"]},
            {"long_name": "England", "types": ["country"]},
        ],
    }
]

_MOCK_GEOCODE_NO_LOCALITY = [
    {
        "formatted_address": "Some Stadium, UK",
        "geometry": {"location": {"lat": 51.5, "lng": -0.1}},
        "address_components": [
            {"long_name": "England", "types": ["country"]},
        ],
    }
]


def _make_gmaps_mock(geocode_data):
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_cls.return_value = mock_instance
    mock_instance.geocode.return_value = geocode_data
    return mock_cls


class TestIdentifyLocation:
    def test_known_venue_returns_success(self):
        with patch.dict(os.environ, _ENV), \
             patch(_PATCH, _make_gmaps_mock(_MOCK_GEOCODE_RESULT)):
            result = identify_location("Goodison Park")
        assert result["status"] == "success"

    def test_location_extracted_as_city(self):
        with patch.dict(os.environ, _ENV), \
             patch(_PATCH, _make_gmaps_mock(_MOCK_GEOCODE_RESULT)):
            result = identify_location("Goodison Park")
        assert result["location"] == "Liverpool"

    def test_formatted_address_is_populated(self):
        with patch.dict(os.environ, _ENV), \
             patch(_PATCH, _make_gmaps_mock(_MOCK_GEOCODE_RESULT)):
            result = identify_location("Goodison Park")
        assert "Liverpool" in result["formatted_address"]

    def test_coordinates_are_returned(self):
        with patch.dict(os.environ, _ENV), \
             patch(_PATCH, _make_gmaps_mock(_MOCK_GEOCODE_RESULT)):
            result = identify_location("Goodison Park")
        assert "lat" in result
        assert "lng" in result
        assert isinstance(result["lat"], float)
        assert isinstance(result["lng"], float)

    def test_source_text_is_echoed(self):
        with patch.dict(os.environ, _ENV), \
             patch(_PATCH, _make_gmaps_mock(_MOCK_GEOCODE_RESULT)):
            result = identify_location("Goodison Park")
        assert result["source_text"] == "Goodison Park"

    def test_falls_back_to_formatted_address_when_no_locality(self):
        with patch.dict(os.environ, _ENV), \
             patch(_PATCH, _make_gmaps_mock(_MOCK_GEOCODE_NO_LOCALITY)):
            result = identify_location("Some Stadium")
        assert result["status"] == "success"
        assert result["location"] == "Some Stadium, UK"

    def test_no_geocode_results_returns_not_found(self):
        with patch.dict(os.environ, _ENV), \
             patch(_PATCH, _make_gmaps_mock([])):
            result = identify_location("Nonexistent Stadium XYZ")
        assert result["status"] == "not_found"
        assert "error_message" in result

    def test_missing_api_key_returns_error(self):
        env_without_key = {k: v for k, v in os.environ.items()
                           if k != "GOOGLE_MAPS_API_KEY"}
        with patch.dict(os.environ, env_without_key, clear=True):
            result = identify_location("Goodison Park")
        assert result["status"] == "error"
        assert "GOOGLE_MAPS_API_KEY" in result["error_message"]

    def test_empty_venue_text_returns_error(self):
        with patch.dict(os.environ, _ENV), \
             patch(_PATCH, _make_gmaps_mock(_MOCK_GEOCODE_RESULT)):
            result = identify_location("")
        assert result["status"] == "error"

    def test_whitespace_only_returns_error(self):
        with patch.dict(os.environ, _ENV), \
             patch(_PATCH, _make_gmaps_mock(_MOCK_GEOCODE_RESULT)):
            result = identify_location("   ")
        assert result["status"] == "error"

    def test_gmaps_exception_returns_error(self):
        mock_cls = MagicMock()
        mock_cls.side_effect = Exception("geocoding failed")
        with patch.dict(os.environ, _ENV), patch(_PATCH, mock_cls):
            result = identify_location("Emirates Stadium")
        assert result["status"] == "error"
        assert "geocoding failed" in result["error_message"]

    def test_postal_town_used_when_no_locality(self):
        postal_town_result = [
            {
                "formatted_address": "Wembley Stadium, London HA9 0WS, UK",
                "geometry": {"location": {"lat": 51.556, "lng": -0.2796}},
                "address_components": [
                    {"long_name": "Wembley", "types": ["postal_town"]},
                    {"long_name": "England", "types": ["country"]},
                ],
            }
        ]
        with patch.dict(os.environ, _ENV), \
             patch(_PATCH, _make_gmaps_mock(postal_town_result)):
            result = identify_location("Wembley Stadium")
        assert result["status"] == "success"
        assert result["location"] == "Wembley"

"""Tests for tools/identify_location.py.

All calls to googlemaps.Client and google.genai.Client are mocked —
no live network requests.
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_concierge.tools.identify_location import identify_location
from event_concierge.tools.llm_helper_calls import llm_resolve_city

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


# ---------------------------------------------------------------------------
# LLM city-resolution helper tests
# ---------------------------------------------------------------------------

_PATCH_LLM = "event_concierge.tools.llm_helper_calls.genai.Client"
_PATCH_LLM_RESOLVE = "event_concierge.tools.identify_location.llm_resolve_city"

_MOCK_LONDON_GEOCODE = [
    {
        "formatted_address": "London, UK",
        "geometry": {"location": {"lat": 51.5074, "lng": -0.1278}},
        "address_components": [
            {"long_name": "London", "types": ["locality", "political"]},
            {"long_name": "England", "types": ["country"]},
        ],
    }
]


def _make_genai_mock(city_text: str):
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_cls.return_value = mock_instance
    mock_response = MagicMock()
    mock_response.text = city_text
    mock_instance.models.generate_content.return_value = mock_response
    return mock_cls


class TestLlmResolveCity:
    def test_returns_city_on_success(self):
        with patch(_PATCH_LLM, _make_genai_mock("London")):
            result = llm_resolve_city("Arsenal FC")
        assert result == "London"

    def test_strips_whitespace(self):
        with patch(_PATCH_LLM, _make_genai_mock("  London  ")):
            result = llm_resolve_city("Arsenal FC")
        assert result == "London"

    def test_returns_none_on_exception(self):
        mock_cls = MagicMock()
        mock_cls.side_effect = Exception("network error")
        with patch(_PATCH_LLM, mock_cls):
            result = llm_resolve_city("Arsenal FC")
        assert result is None

    def test_returns_none_on_empty_response(self):
        with patch(_PATCH_LLM, _make_genai_mock("")):
            result = llm_resolve_city("Arsenal FC")
        assert result is None


class TestClubNameLlmFallback:
    def test_club_name_resolves_via_llm(self):
        """When the raw geocode fails, Gemini resolves the city and a second
        geocode succeeds."""
        mock_gmaps_cls = MagicMock()
        mock_gmaps_inst = MagicMock()
        mock_gmaps_cls.return_value = mock_gmaps_inst
        mock_gmaps_inst.geocode.side_effect = [[], _MOCK_LONDON_GEOCODE]

        with patch.dict(os.environ, _ENV), \
             patch(_PATCH, mock_gmaps_cls), \
             patch(_PATCH_LLM_RESOLVE, return_value="London"):
            result = identify_location("Arsenal FC")

        assert result["status"] == "success"
        assert result["location"] == "London"

    def test_geocode_called_twice_on_llm_path(self):
        """Exactly two geocode calls: once for raw text, once for LLM city."""
        mock_gmaps_cls = MagicMock()
        mock_gmaps_inst = MagicMock()
        mock_gmaps_cls.return_value = mock_gmaps_inst
        mock_gmaps_inst.geocode.side_effect = [[], _MOCK_LONDON_GEOCODE]

        with patch.dict(os.environ, _ENV), \
             patch(_PATCH, mock_gmaps_cls), \
             patch(_PATCH_LLM_RESOLVE, return_value="London"):
            identify_location("Arsenal FC")

        assert mock_gmaps_inst.geocode.call_count == 2

    def test_both_fail_returns_not_found(self):
        """Returns not_found when both geocode attempts yield nothing."""
        mock_gmaps_cls = MagicMock()
        mock_gmaps_inst = MagicMock()
        mock_gmaps_cls.return_value = mock_gmaps_inst
        mock_gmaps_inst.geocode.return_value = []

        with patch.dict(os.environ, _ENV), \
             patch(_PATCH, mock_gmaps_cls), \
             patch(_PATCH_LLM_RESOLVE, return_value="UnknownCity"):
            result = identify_location("Arsenal FC")

        assert result["status"] == "not_found"

    def test_llm_returns_none_falls_through_to_not_found(self):
        """When the LLM helper returns None, no second geocode is attempted."""
        mock_gmaps_cls = MagicMock()
        mock_gmaps_inst = MagicMock()
        mock_gmaps_cls.return_value = mock_gmaps_inst
        mock_gmaps_inst.geocode.return_value = []

        with patch.dict(os.environ, _ENV), \
             patch(_PATCH, mock_gmaps_cls), \
             patch(_PATCH_LLM_RESOLVE, return_value=None):
            result = identify_location("Arsenal FC")

        assert result["status"] == "not_found"
        assert mock_gmaps_inst.geocode.call_count == 1

    def test_direct_stadium_name_skips_llm(self):
        """A stadium name that geocodes directly must not trigger the LLM."""
        with patch.dict(os.environ, _ENV), \
             patch(_PATCH, _make_gmaps_mock(_MOCK_GEOCODE_RESULT)), \
             patch(_PATCH_LLM_RESOLVE) as mock_llm:
            identify_location("Goodison Park")

        mock_llm.assert_not_called()

    def test_source_text_preserved_after_llm_fallback(self):
        """source_text echoes the original input, not the LLM-resolved city."""
        mock_gmaps_cls = MagicMock()
        mock_gmaps_inst = MagicMock()
        mock_gmaps_cls.return_value = mock_gmaps_inst
        mock_gmaps_inst.geocode.side_effect = [[], _MOCK_LONDON_GEOCODE]

        with patch.dict(os.environ, _ENV), \
             patch(_PATCH, mock_gmaps_cls), \
             patch(_PATCH_LLM_RESOLVE, return_value="London"):
            result = identify_location("Arsenal FC")

        assert result["source_text"] == "Arsenal FC"

"""Shared mock payloads and factory helpers for the test suite."""

from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# football-data.org mock payloads
# ---------------------------------------------------------------------------
MOCK_API_RESPONSE = {
    "matches": [
        {
            "id": 12345,
            "utcDate": "2026-03-14T17:30:00Z",
            "status": "TIMED",
            "venue": "Emirates Stadium, London",
            "homeTeam": {"id": 57, "name": "Arsenal"},
            "awayTeam": {"id": 73, "name": "Tottenham Hotspur"},
            "competition": {"id": 2021, "name": "Premier League"},
        }
    ],
    "resultSet": {"count": 1},
    "filters": {},
}

MOCK_API_EMPTY = {"matches": [], "resultSet": {"count": 0}, "filters": {}}

# Simulates a fixture where the API has not yet assigned a venue (common for
# upcoming fixtures early in the season or before stadium confirmation).
MOCK_API_VENUE_TBC = {
    "matches": [
        {
            "id": 99999,
            "utcDate": "2026-03-14T17:30:00Z",
            "status": "TIMED",
            "venue": None,
            "homeTeam": {"id": 62, "name": "Everton FC"},
            "awayTeam": {"id": 57, "name": "Arsenal"},
            "competition": {"id": 2021, "name": "Premier League"},
        }
    ],
    "resultSet": {"count": 1},
    "filters": {},
}

# ---------------------------------------------------------------------------
# Google Maps mock payloads
# ---------------------------------------------------------------------------
MOCK_GEOCODE = [
    {"geometry": {"location": {"lat": 51.5074, "lng": -0.1278}}}
]

MOCK_PLACES = {
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


def make_gmaps_mock(geocode_data=None, places_data=None):
    """Returns a patched googlemaps.Client class with preset return values."""
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_cls.return_value = mock_instance
    mock_instance.geocode.return_value = (
        MOCK_GEOCODE if geocode_data is None else geocode_data
    )
    mock_instance.places_nearby.return_value = (
        MOCK_PLACES if places_data is None else places_data
    )
    return mock_cls

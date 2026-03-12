import os

import googlemaps


def identify_location(venue_text: str) -> dict:
    """Resolves a venue name or partial address to a usable location string.

    Uses the Google Maps Geocoding API to look up stadium names, venue
    names, or any location text extracted from a fixture response.  The
    returned ``location`` field can be passed directly to find_football_bars.

    Args:
        venue_text: A venue name, stadium name, or partial address extracted
                    from a fixture (e.g. 'Goodison Park', 'Emirates Stadium,
                    London', 'Old Trafford').

    Returns:
        dict: A status field, the normalised location string suitable for
              find_football_bars, the full formatted address from Google Maps,
              and lat/lng coordinates.  Returns an error dict when the venue
              cannot be geocoded or the API key is missing.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return {
            "status": "error",
            "error_message": (
                "GOOGLE_MAPS_API_KEY is not set. "
                "Add it to your .env file and restart the agent."
            ),
        }

    if not venue_text or not venue_text.strip():
        return {
            "status": "error",
            "error_message": "No venue text provided to identify a location.",
        }

    try:
        gmaps = googlemaps.Client(key=api_key)
        results = gmaps.geocode(venue_text.strip())

        if not results:
            return {
                "status": "not_found",
                "error_message": (
                    f"Could not identify a location from '{venue_text}'. "
                    "Please provide a location manually."
                ),
            }

        top = results[0]
        formatted_address = top.get("formatted_address", venue_text)
        latlng = top["geometry"]["location"]

        # Extract a short, human-friendly location: prefer the locality
        # (city/town) component so find_football_bars searches nearby that
        # city rather than the exact stadium coordinates.
        short_location = formatted_address
        for component in top.get("address_components", []):
            if "locality" in component.get("types", []):
                short_location = component["long_name"]
                break
            if "postal_town" in component.get("types", []):
                short_location = component["long_name"]
                break

        return {
            "status": "success",
            "location": short_location,
            "formatted_address": formatted_address,
            "lat": latlng["lat"],
            "lng": latlng["lng"],
            "source_text": venue_text,
        }

    except Exception as exc:
        return {
            "status": "error",
            "error_message": f"Location lookup failed: {exc}",
        }

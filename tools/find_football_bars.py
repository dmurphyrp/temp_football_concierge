import os

import googlemaps


def find_football_bars(location: str, radius_km: int = 5) -> dict:
    """Searches for nearby bars and pubs using the Google Maps Places API.

    Geocodes the supplied location string, then queries Places Nearby for
    bars and pubs within the requested radius, sorted by Google rating.

    Args:
        location: A street address, postcode, or landmark (e.g. 'London Bridge').
        radius_km: Search radius in kilometres.  Defaults to 5.

    Returns:
        dict: A status field and a list of venues sorted by rating, each
              including name, address, Google rating, open-now status,
              business status, and a direct Google Maps link.
              Returns an error dict if the API key is missing or the call fails.
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

    try:
        gmaps = googlemaps.Client(key=api_key)

        geocode_result = gmaps.geocode(location)
        if not geocode_result:
            return {
                "status": "error",
                "error_message": f"Could not geocode location '{location}'.",
            }

        latlng = geocode_result[0]["geometry"]["location"]

        places_result = gmaps.places_nearby(
            location=latlng,
            radius=radius_km * 1000,
            keyword="sports bar pub football",
            type="bar",
        )

        api_status = places_result.get("status")
        if api_status not in ("OK", "ZERO_RESULTS"):
            return {
                "status": "error",
                "error_message": f"Google Places API returned: {api_status}",
            }

        venues = []
        for place in places_result.get("results", []):
            opening_hours = place.get("opening_hours") or {}
            venues.append({
                "venue_id": place.get("place_id", ""),
                "name": place.get("name", "Unknown"),
                "address": place.get("vicinity", "Address not listed"),
                "rating": place.get("rating"),
                "user_ratings_total": place.get("user_ratings_total", 0),
                "open_now": opening_hours.get("open_now"),
                "business_status": place.get("business_status", "UNKNOWN"),
                "price_level": place.get("price_level"),
                "maps_url": (
                    f"https://www.google.com/maps/place/?q=place_id:"
                    f"{place.get('place_id', '')}"
                ),
            })

        venues.sort(key=lambda v: v["rating"] or 0, reverse=True)

        return {
            "status": "success",
            "location_searched": location,
            "radius_km": radius_km,
            "venues_found": len(venues),
            "venues": venues,
            "summary": (
                f"Found {len(venues)} bars/pubs within {radius_km}km of "
                f"{location}. Ratings and open status are live from Google Maps."
            ),
        }

    except Exception as exc:
        return {
            "status": "error",
            "error_message": f"Could not search for bars: {exc}",
        }

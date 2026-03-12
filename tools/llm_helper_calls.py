"""LLM helper functions used internally by tools.

Each function here makes a focused, single-purpose call to the Gemini
model to answer a question that cannot be reliably answered by an API
lookup alone (e.g. converting a club name to a city name).  All functions
return ``None`` on any failure so callers can degrade gracefully.
"""

import google.genai as genai

_GEMINI_MODEL = "gemini-2.0-flash"

_RESOLVE_CITY_PROMPT = (
    "What city or town is '{venue}' located in as a football venue? "
    "Reply with only the city name, nothing else."
)


def llm_resolve_city(venue_text: str) -> str | None:
    """Convert a football club or stadium name to its home city.

    Useful when a fixture returns a bare club name (e.g. ``'Arsenal FC'``)
    instead of a geocodable stadium or address.  Gemini resolves this from
    its training knowledge in a single call.

    Args:
        venue_text: A club name, stadium name, or any venue string that
                    failed direct geocoding (e.g. ``'Arsenal FC'``,
                    ``'Manchester City'``).

    Returns:
        The city name as a plain string (e.g. ``'London'``, ``'Manchester'``),
        or ``None`` if the call fails for any reason.
    """
    try:
        client = genai.Client()
        response = client.models.generate_content(
            model=_GEMINI_MODEL,
            contents=_RESOLVE_CITY_PROMPT.format(venue=venue_text),
        )
        city = (response.text or "").strip()
        return city if city else None
    except Exception:
        return None

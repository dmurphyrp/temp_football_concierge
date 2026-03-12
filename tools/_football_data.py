import os

import requests

_BASE_URL = "https://api.football-data.org/v4"


def football_data_get(endpoint: str, params: dict | None = None) -> dict:
    """Call a football-data.org v4 endpoint and return the JSON response.

    Reads FOOTBALL_DATA_API_KEY from the environment for authentication.
    The API works without a key but with heavy rate-limits and restricted
    competitions; a free key lifts these restrictions.
    """
    api_key = os.environ.get("FOOTBALL_DATA_API_KEY", "")
    headers = {}
    if api_key:
        headers["X-Auth-Token"] = api_key
    response = requests.get(
        f"{_BASE_URL}/{endpoint}",
        headers=headers,
        params=params,
        timeout=15,
    )
    response.raise_for_status()
    return response.json()

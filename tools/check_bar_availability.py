_SIMULATED_CAPACITY = 40


def check_bar_availability(venue_name: str, party_size: int, match_time: str) -> dict:
    """Checks whether a bar can accommodate the group for a match.

    Simulates a reservation system check.  In production this would call a
    real booking API (e.g. Google Reserve with Google).  Accepts any party
    up to _SIMULATED_CAPACITY seats.

    Args:
        venue_name: The name of the bar or pub to check.
        party_size: Number of people in the group.
        match_time: ISO-8601 kickoff time string (e.g. '2026-03-14T17:30:00Z').

    Returns:
        dict: A status field, availability flag, simulated seat count, and
              a guidance message if the group is too large.
    """
    can_accommodate = party_size <= _SIMULATED_CAPACITY

    result: dict = {
        "status": "success",
        "venue": venue_name,
        "party_size": party_size,
        "available_seats": _SIMULATED_CAPACITY,
        "can_accommodate": can_accommodate,
        "match_time": match_time,
    }

    if not can_accommodate:
        result["message"] = (
            f"'{venue_name}' cannot accommodate a group of {party_size}. "
            f"Maximum booking size is {_SIMULATED_CAPACITY}. "
            "Consider splitting the group or calling the venue directly."
        )

    return result

_SIMULATED_CAPACITY = 40


def book_table(venue_name: str, party_size: int, match_time: str) -> dict:
    """Books a table at a football bar for the specified party and match time.

    Simulates a reservation confirmation.  Rejects groups larger than
    _SIMULATED_CAPACITY with a clear error so the agent can suggest
    alternatives.

    Args:
        venue_name: Name of the bar or pub to book.
        party_size: Number of people requiring seats.
        match_time: ISO-8601 kickoff time string for the booking slot.

    Returns:
        dict: A status field, booking reference number, and full confirmation
              details, or an error dict if the party is too large.
    """
    if not venue_name or not venue_name.strip():
        return {
            "status": "error",
            "error_message": "Venue name cannot be empty.",
        }

    if party_size > _SIMULATED_CAPACITY:
        return {
            "status": "error",
            "error_message": (
                f"Cannot book {party_size} seats at '{venue_name}'. "
                f"Maximum booking size is {_SIMULATED_CAPACITY}. "
                "Please contact the venue directly for larger groups."
            ),
        }

    booking_ref = f"MC-{abs(hash(venue_name + match_time)) % 100000:05d}"

    return {
        "status": "success",
        "booking_reference": booking_ref,
        "venue": venue_name,
        "party_size": party_size,
        "match_time": match_time,
        "confirmation_message": (
            f"Table booked at {venue_name} for {party_size} people. "
            f"Reference: {booking_ref}. "
            "Arrive 30 minutes before kickoff for the best seats!"
        ),
    }

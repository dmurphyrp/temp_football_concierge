"""Book a table at a football bar via phone call or simulated reservation.

When all five Twilio environment variables are present the tool initiates a
real outbound phone call.  The Gemini Live API (running in the phone bridge
server) conducts the conversation with the venue on the user's behalf.

Required env vars for the phone-call path:
    TWILIO_ACCOUNT_SID   — Twilio account identifier
    TWILIO_AUTH_TOKEN    — Twilio auth token
    TWILIO_PHONE_NUMBER  — Twilio number to call from (E.164 format)
    VENUE_PHONE_NUMBER   — Venue's phone number (E.164 format)
    BRIDGE_SERVER_URL    — Public HTTPS URL of the deployed phone bridge server

If any of those vars are absent the tool falls back to a simulated booking
confirmation so the rest of the agent flow is unaffected during development.
"""

import os
import time
from urllib.parse import urlencode

from twilio.rest import Client as TwilioClient

_SIMULATED_CAPACITY = 40

# Polling configuration for _wait_for_call.
_POLL_INTERVAL_SECONDS: float = 3.0
_CALL_TIMEOUT_SECONDS: int = 120

# A call completing in fewer seconds than this threshold is treated as an
# early disconnection and triggers a retry.
_EARLY_DISCONNECT_THRESHOLD_SECONDS: int = 10

_TERMINAL_STATUSES = frozenset({"completed", "busy", "no-answer", "canceled", "failed"})
_RETRY_STATUSES = frozenset({"no-answer", "busy", "failed"})


def _to_e164(number: str) -> str:
    """Normalise a phone number to E.164 format (leading '+').

    Handles the common '00' international dialing prefix and bare numbers
    that already start with a country code but lack the '+'.
    """
    number = number.strip()
    if number.startswith("+"):
        return number
    if number.startswith("00"):
        return "+" + number[2:]
    return "+" + number


def book_table(venue_name: str, party_size: int, match_time: str) -> dict:
    """Books a table at a football bar for the specified party and match time.

    Initiates a real phone call to the venue when Twilio credentials and the
    bridge server URL are configured, otherwise returns a simulated booking.

    Args:
        venue_name:  Name of the bar or pub to book.
        party_size:  Number of people requiring seats.
        match_time:  ISO-8601 kickoff time string for the booking slot.

    Returns:
        dict: A status field, booking reference, and confirmation details.
              When a call is initiated, also includes call_sid and call_status.
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

    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_PHONE_NUMBER")
    to_number = os.getenv("VENUE_PHONE_NUMBER")
    bridge_url = os.getenv("BRIDGE_SERVER_URL")

    if account_sid and auth_token and from_number and to_number and bridge_url:
        return _book_via_phone_call(
            venue_name, party_size, match_time,
            account_sid, auth_token,
            _to_e164(from_number), _to_e164(to_number), bridge_url,
        )

    return _book_simulated(venue_name, party_size, match_time)


def _book_via_phone_call(
    venue_name: str,
    party_size: int,
    match_time: str,
    account_sid: str,
    auth_token: str,
    from_number: str,
    to_number: str,
    bridge_url: str,
) -> dict:
    """Initiate an outbound Twilio call that uses Gemini to book the table.

    Retries once if the first attempt is not answered, busy, fails to connect,
    or disconnects within _EARLY_DISCONNECT_THRESHOLD_SECONDS seconds.
    """
    try:
        client = TwilioClient(account_sid, auth_token)

        params = urlencode({
            "venue": venue_name,
            "party_size": str(party_size),
            "match_time": match_time,
        })
        webhook_url = f"{bridge_url}/incoming-call?{params}"

        # --- First attempt ---
        call = _initiate_call(client, from_number, to_number, webhook_url)
        final_status, duration = _wait_for_call(client, call.sid)

        # --- Retry once if the call was not answered or disconnected early ---
        if _should_retry(final_status, duration):
            call = _initiate_call(client, from_number, to_number, webhook_url)
            final_status, duration = _wait_for_call(client, call.sid)

        booking_ref = f"MC-{abs(hash(venue_name + match_time)) % 100000:05d}"

        if _should_retry(final_status, duration):
            return {
                "status": "error",
                "error_message": (
                    f"Unable to reach {venue_name} after 2 attempts. "
                    f"Last call status: {final_status}. "
                    "Please try calling the venue directly."
                ),
            }

        return {
            "status": "success",
            "booking_reference": booking_ref,
            "venue": venue_name,
            "party_size": party_size,
            "match_time": match_time,
            "call_sid": call.sid,
            "call_status": final_status,
            "confirmation_message": (
                f"Phone booking call completed for {venue_name} — "
                f"{party_size} people at {match_time}. "
                f"Reference: {booking_ref}. "
                "The AI assistant has spoken with the venue to confirm your table."
            ),
        }
    except Exception as exc:
        return {
            "status": "error",
            "error_message": f"Phone booking failed: {exc}",
        }


def _initiate_call(client, from_number: str, to_number: str, webhook_url: str):
    """Create a new Twilio outbound call and return the Call resource."""
    return client.calls.create(
        to=to_number,
        from_=from_number,
        url=webhook_url,
    )


def _wait_for_call(client, call_sid: str) -> tuple[str, int]:
    """Poll Twilio until the call reaches a terminal status.

    Returns:
        A (status, duration_seconds) tuple where duration is 0 for calls
        that never connected.
    """
    deadline = time.time() + _CALL_TIMEOUT_SECONDS
    while time.time() < deadline:
        fetched = client.calls(call_sid).fetch()
        if fetched.status in _TERMINAL_STATUSES:
            return fetched.status, int(fetched.duration or 0)
        time.sleep(_POLL_INTERVAL_SECONDS)
    # Timed out — fetch once more and return whatever state we see.
    fetched = client.calls(call_sid).fetch()
    return fetched.status, int(fetched.duration or 0)


def _should_retry(status: str, duration: int) -> bool:
    """Return True if the call outcome warrants a single retry attempt."""
    if status in _RETRY_STATUSES:
        return True
    if status == "completed" and duration < _EARLY_DISCONNECT_THRESHOLD_SECONDS:
        return True
    return False


def _book_simulated(venue_name: str, party_size: int, match_time: str) -> dict:
    """Return a simulated booking confirmation (no external calls)."""
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

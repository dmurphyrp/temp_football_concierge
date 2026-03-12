"""Tests for the phone-call path in tools/book_table.py.

All Twilio API calls are mocked — no real network or telephony requests.
The phone-call path is activated when five env vars are present:
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER,
  VENUE_PHONE_NUMBER, BRIDGE_SERVER_URL.
When any of those are absent the function falls back to simulation.
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_concierge.tools.book_table import book_table
from event_concierge.tools.check_bar_availability import _SIMULATED_CAPACITY

_KICKOFF = "2026-03-14T17:30:00Z"

_TWILIO_ENV = {
    "TWILIO_ACCOUNT_SID": "ACtest123",
    "TWILIO_AUTH_TOKEN": "test_auth_token",
    "TWILIO_PHONE_NUMBER": "+15551234567",
    "VENUE_PHONE_NUMBER": "+35383000000",
    "BRIDGE_SERVER_URL": "https://bridge.example.com",
}

_PATCH_CLIENT = "event_concierge.tools.book_table.TwilioClient"


def _make_twilio_mock(
    call_sid: str = "CA123456",
    call_status: str = "queued",
    final_status: str = "completed",
    final_duration: int = 60,
) -> MagicMock:
    """Return a mock Twilio Client.

    Supports both calls.create() (initial call creation) and
    calls(sid).fetch() (status polling used by _wait_for_call).
    """
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_cls.return_value = mock_instance

    mock_call = MagicMock()
    mock_call.sid = call_sid
    mock_call.status = call_status
    mock_instance.calls.create.return_value = mock_call

    # calls(call_sid).fetch() — returns a terminal status immediately
    fetched = MagicMock()
    fetched.status = final_status
    fetched.duration = str(final_duration)
    mock_instance.calls.return_value.fetch.return_value = fetched

    return mock_cls


def _make_retry_mock(
    first_status: str,
    first_duration: int = 0,
    second_status: str = "completed",
    second_duration: int = 60,
) -> MagicMock:
    """Return a mock Twilio Client that simulates a retry scenario.

    The first call attempt produces first_status; the second produces
    second_status.  Supports both calls.create() and calls(sid).fetch().
    """
    mock_cls = MagicMock()
    mock_instance = MagicMock()
    mock_cls.return_value = mock_instance

    call1 = MagicMock()
    call1.sid = "CA111"
    call1.status = "queued"

    call2 = MagicMock()
    call2.sid = "CA222"
    call2.status = "queued"

    # Return a different Call object on each create() invocation.
    mock_instance.calls.create.side_effect = [call1, call2]

    fetched1 = MagicMock()
    fetched1.status = first_status
    fetched1.duration = str(first_duration)

    fetched2 = MagicMock()
    fetched2.status = second_status
    fetched2.duration = str(second_duration)

    def _calls_by_sid(call_sid):
        resource = MagicMock()
        resource.fetch.return_value = fetched1 if call_sid == "CA111" else fetched2
        return resource

    # side_effect on calls only affects calls(...) — calls.create is unaffected.
    mock_instance.calls.side_effect = _calls_by_sid

    return mock_cls


# ---------------------------------------------------------------------------
# Existing phone-call behaviour tests
# ---------------------------------------------------------------------------

class TestBookTablePhoneCall:
    """Tests for book_table when Twilio credentials are present in env vars."""

    def test_returns_success_when_call_initiated(self):
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, _make_twilio_mock()):
            result = book_table("Pitch & Pint", 4, _KICKOFF)
        assert result["status"] == "success"

    def test_result_contains_call_sid(self):
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, _make_twilio_mock(call_sid="CA-abc-123")):
            result = book_table("Pitch & Pint", 4, _KICKOFF)
        assert result["call_sid"] == "CA-abc-123"

    def test_result_contains_final_call_status(self):
        """call_status reflects the terminal status after polling, not 'queued'."""
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, _make_twilio_mock(final_status="completed")):
            result = book_table("Pitch & Pint", 4, _KICKOFF)
        assert result["call_status"] == "completed"

    def test_result_contains_booking_reference(self):
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, _make_twilio_mock()):
            result = book_table("Pitch & Pint", 4, _KICKOFF)
        assert "booking_reference" in result
        assert result["booking_reference"].startswith("MC-")

    def test_booking_reference_is_deterministic(self):
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, _make_twilio_mock()):
            r1 = book_table("Pitch & Pint", 4, _KICKOFF)
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, _make_twilio_mock()):
            r2 = book_table("Pitch & Pint", 4, _KICKOFF)
        assert r1["booking_reference"] == r2["booking_reference"]

    def test_twilio_client_created_with_credentials(self):
        mock_cls = _make_twilio_mock()
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            book_table("Pitch & Pint", 4, _KICKOFF)
        mock_cls.assert_called_once_with(
            _TWILIO_ENV["TWILIO_ACCOUNT_SID"],
            _TWILIO_ENV["TWILIO_AUTH_TOKEN"],
        )

    def test_twilio_called_with_venue_phone_number(self):
        mock_cls = _make_twilio_mock()
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            book_table("Pitch & Pint", 4, _KICKOFF)
        call_kwargs = mock_cls.return_value.calls.create.call_args[1]
        assert call_kwargs["to"] == _TWILIO_ENV["VENUE_PHONE_NUMBER"]

    def test_twilio_called_from_configured_number(self):
        mock_cls = _make_twilio_mock()
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            book_table("Pitch & Pint", 4, _KICKOFF)
        call_kwargs = mock_cls.return_value.calls.create.call_args[1]
        assert call_kwargs["from_"] == _TWILIO_ENV["TWILIO_PHONE_NUMBER"]

    def test_webhook_url_points_to_bridge_server(self):
        mock_cls = _make_twilio_mock()
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            book_table("Pitch & Pint", 4, _KICKOFF)
        call_kwargs = mock_cls.return_value.calls.create.call_args[1]
        assert "bridge.example.com" in call_kwargs["url"]

    def test_webhook_url_targets_incoming_call_endpoint(self):
        mock_cls = _make_twilio_mock()
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            book_table("Pitch & Pint", 4, _KICKOFF)
        call_kwargs = mock_cls.return_value.calls.create.call_args[1]
        assert "/incoming-call" in call_kwargs["url"]

    def test_webhook_url_contains_venue_name(self):
        mock_cls = _make_twilio_mock()
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            book_table("TheAnchor", 4, _KICKOFF)
        call_kwargs = mock_cls.return_value.calls.create.call_args[1]
        assert "TheAnchor" in call_kwargs["url"]

    def test_webhook_url_contains_party_size(self):
        mock_cls = _make_twilio_mock()
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            book_table("Pitch & Pint", 7, _KICKOFF)
        call_kwargs = mock_cls.return_value.calls.create.call_args[1]
        assert "7" in call_kwargs["url"]

    def test_venue_is_echoed_in_result(self):
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, _make_twilio_mock()):
            result = book_table("The Anchor", 4, _KICKOFF)
        assert result["venue"] == "The Anchor"

    def test_party_size_echoed_in_result(self):
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, _make_twilio_mock()):
            result = book_table("Pitch & Pint", 6, _KICKOFF)
        assert result["party_size"] == 6

    def test_match_time_echoed_in_result(self):
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, _make_twilio_mock()):
            result = book_table("Pitch & Pint", 4, _KICKOFF)
        assert result["match_time"] == _KICKOFF

    def test_confirmation_message_is_present(self):
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, _make_twilio_mock()):
            result = book_table("Pitch & Pint", 4, _KICKOFF)
        assert "confirmation_message" in result
        assert len(result["confirmation_message"]) > 0

    def test_twilio_exception_returns_error(self):
        mock_cls = MagicMock()
        mock_cls.return_value.calls.create.side_effect = Exception("Network failure")
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            result = book_table("Pitch & Pint", 4, _KICKOFF)
        assert result["status"] == "error"
        assert "error_message" in result

    def test_over_capacity_returns_error_without_calling_twilio(self):
        mock_cls = _make_twilio_mock()
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            result = book_table("Pitch & Pint", _SIMULATED_CAPACITY + 1, _KICKOFF)
        assert result["status"] == "error"
        mock_cls.return_value.calls.create.assert_not_called()

    def test_empty_venue_returns_error_without_calling_twilio(self):
        mock_cls = _make_twilio_mock()
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            result = book_table("", 4, _KICKOFF)
        assert result["status"] == "error"
        mock_cls.return_value.calls.create.assert_not_called()


# ---------------------------------------------------------------------------
# Retry-on-failure tests
# ---------------------------------------------------------------------------

class TestBookTableRetry:
    """Tests for retry-once-on-failure behaviour."""

    def test_retries_when_call_not_answered(self):
        """no-answer on first attempt triggers a second call."""
        mock_cls = _make_retry_mock("no-answer")
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            book_table("Pitch & Pint", 4, _KICKOFF)
        assert mock_cls.return_value.calls.create.call_count == 2

    def test_retries_on_busy(self):
        """Busy signal on first attempt triggers a second call."""
        mock_cls = _make_retry_mock("busy")
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            book_table("Pitch & Pint", 4, _KICKOFF)
        assert mock_cls.return_value.calls.create.call_count == 2

    def test_retries_on_call_failure(self):
        """Call failure on first attempt triggers a second call."""
        mock_cls = _make_retry_mock("failed")
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            book_table("Pitch & Pint", 4, _KICKOFF)
        assert mock_cls.return_value.calls.create.call_count == 2

    def test_retries_on_early_disconnect(self):
        """A call completing below the disconnect threshold triggers a retry."""
        from event_concierge.tools.book_table import _EARLY_DISCONNECT_THRESHOLD_SECONDS
        short_duration = _EARLY_DISCONNECT_THRESHOLD_SECONDS - 1
        mock_cls = _make_retry_mock("completed", first_duration=short_duration)
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            book_table("Pitch & Pint", 4, _KICKOFF)
        assert mock_cls.return_value.calls.create.call_count == 2

    def test_does_not_retry_on_normal_completion(self):
        """A completed call with normal duration does NOT trigger a retry."""
        mock_cls = _make_twilio_mock(final_status="completed", final_duration=60)
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            book_table("Pitch & Pint", 4, _KICKOFF)
        assert mock_cls.return_value.calls.create.call_count == 1

    def test_returns_success_when_retry_succeeds(self):
        """If the retry call completes normally, the result is success."""
        mock_cls = _make_retry_mock("no-answer")
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            result = book_table("Pitch & Pint", 4, _KICKOFF)
        assert result["status"] == "success"

    def test_returns_error_after_two_failures(self):
        """If both attempts fail, an error dict is returned."""
        mock_cls = _make_retry_mock("no-answer", second_status="no-answer")
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            result = book_table("Pitch & Pint", 4, _KICKOFF)
        assert result["status"] == "error"
        assert "error_message" in result

    def test_error_message_after_two_failures_mentions_venue(self):
        """The error message after two failures references the venue name."""
        mock_cls = _make_retry_mock("no-answer", second_status="no-answer")
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            result = book_table("Pitch & Pint", 4, _KICKOFF)
        assert "Pitch & Pint" in result["error_message"]

    def test_error_message_after_two_failures_mentions_attempts(self):
        """The error message communicates that multiple attempts were made."""
        mock_cls = _make_retry_mock("busy", second_status="busy")
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            result = book_table("Pitch & Pint", 4, _KICKOFF)
        msg = result["error_message"].lower()
        assert "2" in msg or "attempt" in msg or "twice" in msg

    def test_does_not_make_more_than_two_attempts(self):
        """Exactly two calls are made regardless of outcome."""
        mock_cls = _make_retry_mock("busy", second_status="busy")
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            book_table("Pitch & Pint", 4, _KICKOFF)
        assert mock_cls.return_value.calls.create.call_count == 2

    def test_call_sid_in_success_result_is_from_last_attempt(self):
        """On a retry, the call_sid in the result belongs to the second call."""
        mock_cls = _make_retry_mock("no-answer")
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            result = book_table("Pitch & Pint", 4, _KICKOFF)
        assert result["call_sid"] == "CA222"


# ---------------------------------------------------------------------------
# E.164 normalisation tests
# ---------------------------------------------------------------------------

class TestPhoneNumberNormalisation:
    """Phone numbers with '00' international prefix are converted to E.164."""

    def test_00_prefix_normalised_to_plus(self):
        """00353... is sent to Twilio as +353..."""
        env_with_00 = {**_TWILIO_ENV, "VENUE_PHONE_NUMBER": "00353834631171"}
        mock_cls = _make_twilio_mock()
        with patch.dict(os.environ, env_with_00), patch(_PATCH_CLIENT, mock_cls):
            book_table("Pitch & Pint", 4, _KICKOFF)
        call_kwargs = mock_cls.return_value.calls.create.call_args[1]
        assert call_kwargs["to"] == "+353834631171"

    def test_plus_prefix_left_unchanged(self):
        """Numbers already in E.164 are not altered."""
        mock_cls = _make_twilio_mock()
        with patch.dict(os.environ, _TWILIO_ENV), patch(_PATCH_CLIENT, mock_cls):
            book_table("Pitch & Pint", 4, _KICKOFF)
        call_kwargs = mock_cls.return_value.calls.create.call_args[1]
        assert call_kwargs["to"] == _TWILIO_ENV["VENUE_PHONE_NUMBER"]

    def test_from_number_00_prefix_normalised(self):
        """The FROM number is also normalised."""
        env_with_00 = {**_TWILIO_ENV, "TWILIO_PHONE_NUMBER": "0012722957471"}
        mock_cls = _make_twilio_mock()
        with patch.dict(os.environ, env_with_00), patch(_PATCH_CLIENT, mock_cls):
            book_table("Pitch & Pint", 4, _KICKOFF)
        call_kwargs = mock_cls.return_value.calls.create.call_args[1]
        assert call_kwargs["from_"] == "+12722957471"

    def test_bare_number_gets_plus_prefix(self):
        """A number with no prefix gets '+' prepended."""
        env_bare = {**_TWILIO_ENV, "VENUE_PHONE_NUMBER": "353834631171"}
        mock_cls = _make_twilio_mock()
        with patch.dict(os.environ, env_bare), patch(_PATCH_CLIENT, mock_cls):
            book_table("Pitch & Pint", 4, _KICKOFF)
        call_kwargs = mock_cls.return_value.calls.create.call_args[1]
        assert call_kwargs["to"] == "+353834631171"


# ---------------------------------------------------------------------------
# Fallback-to-simulation tests
# ---------------------------------------------------------------------------

class TestBookTableFallsBackToSimulation:
    """book_table uses simulation when any Twilio env var is absent."""

    _NO_TWILIO = {
        k: v for k, v in os.environ.items()
        if k not in _TWILIO_ENV
    }

    def test_missing_all_creds_still_returns_success(self):
        with patch.dict(os.environ, self._NO_TWILIO, clear=True):
            result = book_table("Pitch & Pint", 4, _KICKOFF)
        assert result["status"] == "success"

    def test_simulation_result_has_no_call_sid(self):
        with patch.dict(os.environ, self._NO_TWILIO, clear=True):
            result = book_table("Pitch & Pint", 4, _KICKOFF)
        assert "call_sid" not in result

    def test_partial_creds_falls_back_to_simulation(self):
        partial = {**self._NO_TWILIO, "TWILIO_ACCOUNT_SID": "ACtest"}
        with patch.dict(os.environ, partial, clear=True):
            result = book_table("Pitch & Pint", 4, _KICKOFF)
        assert result["status"] == "success"
        assert "call_sid" not in result

    def test_simulation_still_returns_booking_reference(self):
        with patch.dict(os.environ, self._NO_TWILIO, clear=True):
            result = book_table("Pitch & Pint", 4, _KICKOFF)
        assert result["booking_reference"].startswith("MC-")

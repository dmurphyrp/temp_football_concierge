"""Tests for phone_bridge/server.py — FastAPI bridge server.

The server bridges Twilio (PSTN) phone calls to the Gemini Live API.

HTTP endpoints tested here:
  GET  /health          — liveness probe
  POST /incoming-call   — returns TwiML that opens a media stream

Helper function tested here:
  build_booking_prompt  — constructs the Gemini system prompt from booking params

WebSocket endpoint tested here:
  WS /media-stream      — accepts Twilio audio, forwards to Gemini, relays back

All Gemini Live API calls are mocked.
"""

import asyncio
import base64
import json
import os
import sys
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from event_concierge.phone_bridge.server import app, build_booking_prompt

_CLIENT = TestClient(app)
_KICKOFF = "2026-03-14T17:30:00Z"
_PATCH_FACTORY = "event_concierge.phone_bridge.server._gemini_session_factory"


# ---------------------------------------------------------------------------
# Lightweight mock Gemini session used by WebSocket tests
# ---------------------------------------------------------------------------

class _MockGeminiSession:
    """Minimal stand-in for GeminiLiveSession: records sends, blocks on receive.

    receive() blocks until cancelled.  This mirrors real Gemini behaviour
    (streaming is open-ended) and ensures the Twilio relay task can process
    all inbound messages before asyncio.wait(FIRST_COMPLETED) fires.
    """

    def __init__(self):
        self.sent_chunks: list[bytes] = []

    async def send(self, pcm_bytes: bytes) -> None:
        self.sent_chunks.append(pcm_bytes)

    async def receive(self):
        """Async generator that blocks until the task is cancelled."""
        await asyncio.sleep(float("inf"))
        return
        yield  # makes this an async generator


@asynccontextmanager
async def _mock_session_factory(prompt: str):
    yield _MockGeminiSession()


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_returns_200(self):
        resp = _CLIENT.get("/health")
        assert resp.status_code == 200

    def test_body_has_ok_status(self):
        resp = _CLIENT.get("/health")
        assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# /incoming-call
# ---------------------------------------------------------------------------

class TestIncomingCallEndpoint:
    def test_returns_200(self):
        resp = _CLIENT.post(
            f"/incoming-call?venue=Pitch+%26+Pint&party_size=4&match_time={_KICKOFF}"
        )
        assert resp.status_code == 200

    def test_content_type_is_xml(self):
        resp = _CLIENT.post("/incoming-call")
        assert "xml" in resp.headers["content-type"]

    def test_response_wraps_in_twiml_response_element(self):
        resp = _CLIENT.post("/incoming-call")
        assert "<Response>" in resp.text

    def test_response_contains_connect_element(self):
        resp = _CLIENT.post("/incoming-call")
        assert "<Connect>" in resp.text

    def test_response_contains_stream_element(self):
        resp = _CLIENT.post("/incoming-call")
        assert "<Stream" in resp.text

    def test_stream_url_targets_media_stream_path(self):
        resp = _CLIENT.post("/incoming-call")
        assert "media-stream" in resp.text

    def test_stream_url_uses_websocket_scheme(self):
        resp = _CLIENT.post("/incoming-call")
        # Should use ws:// or wss://
        assert "ws://" in resp.text or "wss://" in resp.text

    def test_stream_url_uses_wss_when_x_forwarded_proto_is_https(self):
        """Cloud Run sets X-Forwarded-Proto: https; stream must use wss://."""
        resp = _CLIENT.post(
            "/incoming-call",
            headers={"x-forwarded-proto": "https"},
        )
        assert "wss://" in resp.text

    def test_stream_url_uses_ws_without_forwarded_proto(self):
        """Local dev without a proxy still uses plain ws://."""
        resp = _CLIENT.post("/incoming-call")
        assert "ws://" in resp.text

    def test_venue_param_forwarded_as_twiml_parameter(self):
        resp = _CLIENT.post("/incoming-call?venue=TheAnchor")
        assert "TheAnchor" in resp.text
        assert "<Parameter" in resp.text

    def test_party_size_forwarded_as_twiml_parameter(self):
        resp = _CLIENT.post("/incoming-call?party_size=8")
        assert "8" in resp.text
        assert "<Parameter" in resp.text

    def test_missing_params_still_returns_valid_twiml(self):
        resp = _CLIENT.post("/incoming-call")
        assert resp.status_code == 200
        assert "<Response>" in resp.text

    def test_ampersand_in_venue_name_is_xml_escaped(self):
        """Venue names like 'Pitch & Pint' must not break the XML document."""
        resp = _CLIENT.post("/incoming-call?venue=Pitch+%26+Pint&party_size=4")
        assert resp.status_code == 200
        # Raw & inside an XML attribute would be invalid — must be &amp;
        xml_body = resp.text
        # The document must parse cleanly (no bare & in attribute values)
        import xml.etree.ElementTree as ET
        try:
            ET.fromstring(xml_body)
            parsed_ok = True
        except ET.ParseError:
            parsed_ok = False
        assert parsed_ok, f"TwiML is not valid XML: {xml_body}"

    def test_stream_url_has_no_query_params(self):
        """Parameters are passed via <Parameter> elements, not in the stream URL."""
        resp = _CLIENT.post("/incoming-call?venue=TheAnchor&party_size=4")
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.text)
        ns = ""
        stream = root.find(f".//{ns}Stream")
        assert "?" not in stream.attrib["url"]


# ---------------------------------------------------------------------------
# build_booking_prompt
# ---------------------------------------------------------------------------

class TestBuildBookingPrompt:
    def test_contains_venue_name(self):
        p = build_booking_prompt("Pitch & Pint", 4, _KICKOFF)
        assert "Pitch & Pint" in p

    def test_contains_party_size(self):
        p = build_booking_prompt("Pitch & Pint", 4, _KICKOFF)
        assert "4" in p

    def test_contains_match_time(self):
        p = build_booking_prompt("Pitch & Pint", 4, _KICKOFF)
        assert "2026-03-14" in p

    def test_instructs_to_book_a_table(self):
        p = build_booking_prompt("Any Bar", 6, _KICKOFF)
        assert any(w in p.lower() for w in ("book", "reservation", "table"))

    def test_instructs_polite_goodbye(self):
        p = build_booking_prompt("Any Bar", 6, _KICKOFF)
        assert any(w in p.lower() for w in ("goodbye", "thank", "polite"))

    def test_different_venues_produce_different_prompts(self):
        p1 = build_booking_prompt("Bar A", 4, _KICKOFF)
        p2 = build_booking_prompt("Bar B", 4, _KICKOFF)
        assert p1 != p2

    def test_different_party_sizes_produce_different_prompts(self):
        p1 = build_booking_prompt("Bar A", 4, _KICKOFF)
        p2 = build_booking_prompt("Bar A", 8, _KICKOFF)
        assert p1 != p2

    def test_is_non_empty_string(self):
        p = build_booking_prompt("Bar", 2, _KICKOFF)
        assert isinstance(p, str) and len(p) > 0


# ---------------------------------------------------------------------------
# build_booking_prompt — venue verification tests
# ---------------------------------------------------------------------------

class TestBuildBookingPromptVenueVerification:
    """The prompt must instruct Gemini to verify it has reached the right venue."""

    def test_prompt_instructs_to_confirm_venue_name(self):
        """Gemini should open by confirming it is speaking with the target venue."""
        p = build_booking_prompt("Pitch & Pint", 4, _KICKOFF)
        assert any(w in p.lower() for w in ("confirm", "reached", "speaking with", "am i"))

    def test_prompt_instructs_to_clarify_if_different_venue(self):
        """Gemini should ask for clarification if the venue name seems wrong."""
        p = build_booking_prompt("Pitch & Pint", 4, _KICKOFF)
        assert any(w in p.lower() for w in ("clarif", "confirm the name", "different", "wrong"))

    def test_prompt_instructs_to_apologise_for_wrong_venue(self):
        """Gemini must apologise when confirmed it has the wrong number."""
        p = build_booking_prompt("Pitch & Pint", 4, _KICKOFF)
        assert any(w in p.lower() for w in ("apologise", "apologize", "sorry", "wrong number"))

    def test_prompt_instructs_to_end_call_for_wrong_venue(self):
        """Gemini must end the call if it is the wrong venue."""
        p = build_booking_prompt("Pitch & Pint", 4, _KICKOFF)
        assert any(w in p.lower() for w in ("end the call", "end call", "hang up", "goodbye"))

    def test_prompt_instructs_to_proceed_if_venue_confirmed_correct(self):
        """Gemini should continue with the booking when the venue is confirmed."""
        p = build_booking_prompt("Pitch & Pint", 4, _KICKOFF)
        assert any(w in p.lower() for w in ("proceed", "correct", "confirmed", "continue"))


# ---------------------------------------------------------------------------
# /media-stream WebSocket
# ---------------------------------------------------------------------------

def _twilio_start_event(
    stream_sid: str = "MZ_test_sid",
    venue: str = "Bar",
    party_size: str = "4",
    match_time: str = _KICKOFF,
) -> str:
    """Build a Twilio "start" event JSON string with customParameters."""
    return json.dumps({
        "event": "start",
        "sequenceNumber": "1",
        "streamSid": stream_sid,
        "start": {
            "accountSid": "AC_test",
            "streamSid": stream_sid,
            "callSid": "CA_test",
            "tracks": ["inbound"],
            "mediaFormat": {"encoding": "audio/x-mulaw", "sampleRate": 8000, "channels": 1},
            "customParameters": {
                "venue": venue,
                "party_size": party_size,
                "match_time": match_time,
            },
        },
    })


class TestMediaStreamWebSocket:
    def test_websocket_endpoint_is_registered(self):
        routes = {r.path for r in app.routes}
        assert "/media-stream" in routes

    def test_websocket_accepts_connection(self):
        with patch(_PATCH_FACTORY, _mock_session_factory):
            with TestClient(app) as client:
                with client.websocket_connect("/media-stream") as ws:
                    ws.send_text(_twilio_start_event())
                    ws.send_text(json.dumps({"event": "stop"}))

    def test_websocket_accepts_twilio_connected_event(self):
        with patch(_PATCH_FACTORY, _mock_session_factory):
            with TestClient(app) as client:
                with client.websocket_connect("/media-stream") as ws:
                    ws.send_text(json.dumps({
                        "event": "connected",
                        "protocol": "Call",
                        "version": "1.0.0",
                    }))
                    ws.send_text(_twilio_start_event())
                    ws.send_text(json.dumps({"event": "stop"}))

    def test_websocket_forwards_audio_to_gemini(self):
        session = _MockGeminiSession()

        @asynccontextmanager
        async def capturing_factory(prompt: str):
            yield session

        mulaw_payload = base64.b64encode(b"\x7f" * 160).decode()

        with patch(_PATCH_FACTORY, capturing_factory):
            with TestClient(app) as client:
                with client.websocket_connect("/media-stream") as ws:
                    ws.send_text(_twilio_start_event())
                    ws.send_text(json.dumps({
                        "event": "media",
                        "media": {"payload": mulaw_payload},
                    }))
                    ws.send_text(json.dumps({"event": "stop"}))

        assert len(session.sent_chunks) > 0

    def test_websocket_sends_pcm_not_mulaw_to_gemini(self):
        """Audio forwarded to Gemini must be PCM (wider, not 1 byte/sample)."""
        session = _MockGeminiSession()

        @asynccontextmanager
        async def capturing_factory(prompt: str):
            yield session

        mulaw_payload = base64.b64encode(b"\x7f" * 160).decode()

        with patch(_PATCH_FACTORY, capturing_factory):
            with TestClient(app) as client:
                with client.websocket_connect("/media-stream") as ws:
                    ws.send_text(_twilio_start_event())
                    ws.send_text(json.dumps({
                        "event": "media",
                        "media": {"payload": mulaw_payload},
                    }))
                    ws.send_text(json.dumps({"event": "stop"}))

        # 160 mu-law bytes → PCM 16 kHz must be significantly larger
        assert all(len(chunk) > 160 for chunk in session.sent_chunks)

    def test_gemini_session_receives_booking_prompt(self):
        received_prompts: list[str] = []

        @asynccontextmanager
        async def capturing_factory(prompt: str):
            received_prompts.append(prompt)
            yield _MockGeminiSession()

        with patch(_PATCH_FACTORY, capturing_factory):
            with TestClient(app) as client:
                with client.websocket_connect("/media-stream") as ws:
                    ws.send_text(_twilio_start_event(
                        venue="Pitch & Pint", party_size="5",
                    ))
                    ws.send_text(json.dumps({"event": "stop"}))

        assert len(received_prompts) == 1
        assert "Pitch & Pint" in received_prompts[0]
        assert "5" in received_prompts[0]

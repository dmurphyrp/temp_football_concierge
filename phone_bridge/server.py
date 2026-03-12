"""FastAPI bridge server — connects Twilio phone calls to the Gemini Live API.

Architecture
------------
1. Twilio initiates an outbound call to the venue's phone number.
2. When the call connects, Twilio POSTs to /incoming-call with booking params
   in the query string.
3. /incoming-call returns TwiML that instructs Twilio to open a WebSocket
   media stream to /media-stream.
4. /media-stream bridges the two sides:
     Twilio  →  (G.711 mu-law 8 kHz)  →  transcode  →  Gemini Live API
     Gemini  →  (PCM 24 kHz)          →  transcode  →  Twilio

Deployment
----------
Deploy this module to Google Cloud Run so it gets a public HTTPS/WSS URL.
Set the BRIDGE_SERVER_URL secret in Secret Manager to that URL so that
book_table.py can reference it when creating the Twilio call.
"""

import asyncio
import base64
import json
import logging
import os
from xml.sax.saxutils import escape as xml_escape

logging.basicConfig(level=logging.INFO, force=True)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import Response

from .audio import mulaw_to_pcm, pcm_to_mulaw
from .gemini_session import create_live_session

app = FastAPI(title="Matchday Concierge Phone Bridge")

# Overridable in tests — replace with a mock async context manager factory.
_gemini_session_factory = create_live_session


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def build_booking_prompt(venue_name: str, party_size: int, match_time: str) -> str:
    """Build the Gemini system prompt for a table-booking phone call.

    Args:
        venue_name:  Name of the bar or pub being called.
        party_size:  Number of people to book for.
        match_time:  ISO-8601 kickoff time string.

    Returns:
        A multi-sentence system instruction for the Gemini Live session.
    """
    return (
        f"You are a polite and friendly booking assistant calling {venue_name} "
        f"on behalf of a football fan. "
        f"Your goal is to book a table for {party_size} people for a football "
        f"match at {match_time}.\n\n"

        f"STEP 1 — Confirm you have reached the correct premises:\n"
        f"When the call is answered, confirm you are speaking with {venue_name}. "
        f"For example: 'Hi, am I speaking with {venue_name}?'\n\n"

        f"If the person identifies the premises as a different venue:\n"
        f"  - Ask them to clarify: 'Could you confirm the name of your establishment?'\n"
        f"  - If they confirm it is NOT {venue_name}: apologise sincerely — explain you "
        f"must have the wrong number — say goodbye politely, and end the call.\n"
        f"  - If they confirm it IS {venue_name} despite any initial confusion: "
        f"proceed with the booking.\n\n"

        f"STEP 2 — Make the reservation:\n"
        f"Once you have confirmed you are speaking with {venue_name}, ask to make a "
        f"table reservation for {party_size} people at {match_time}. "
        f"Be concise — get straight to the point while remaining warm and friendly. "
        f"If they confirm the booking, note any reference number they provide. "
        f"If they cannot accommodate the group, thank them for their time.\n\n"

        f"STEP 3 — Close the call:\n"
        f"Once the booking is settled (confirmed, declined, or wrong venue identified), "
        f"say a polite goodbye and end the conversation."
    )


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Liveness probe used by Cloud Run."""
    return {"status": "ok"}


@app.post("/incoming-call")
async def incoming_call(request: Request):
    """Handle Twilio's POST when a call connects.

    Reads booking parameters from the query string and returns TwiML that
    instructs Twilio to open a bidirectional audio stream to /media-stream.
    Booking parameters are passed as <Parameter> elements so they arrive in
    the Twilio "start" event's customParameters field.
    """
    venue = request.query_params.get("venue", "the venue")
    party_size = request.query_params.get("party_size", "your group")
    match_time = request.query_params.get("match_time", "the event")

    host = request.headers.get("host", "localhost")
    forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    scheme = "wss" if forwarded_proto == "https" else "ws"
    stream_url = f"{scheme}://{host}/media-stream"

    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        "<Connect>"
        f'<Stream url="{xml_escape(stream_url)}">'
        f'<Parameter name="venue" value="{xml_escape(str(venue))}" />'
        f'<Parameter name="party_size" value="{xml_escape(str(party_size))}" />'
        f'<Parameter name="match_time" value="{xml_escape(str(match_time))}" />'
        "</Stream>"
        "</Connect>"
        "</Response>"
    )
    return Response(content=twiml, media_type="application/xml")


# ---------------------------------------------------------------------------
# WebSocket endpoint — bidirectional audio relay
# ---------------------------------------------------------------------------

@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    """Relay audio bidirectionally between Twilio and the Gemini Live API.

    Booking parameters and the streamSid arrive in the Twilio "start" event
    (via <Parameter> elements in TwiML), not as WebSocket query params.
    """
    await websocket.accept()

    stream_sid = ""
    venue = ""
    party_size = 4
    match_time = ""

    while True:
        raw = await websocket.receive_text()
        data = json.loads(raw)
        event_type = data.get("event")
        if event_type == "start":
            stream_sid = data.get("streamSid", "")
            custom = data.get("start", {}).get("customParameters", {})
            venue = custom.get("venue", "the venue")
            party_size = int(custom.get("party_size", "4"))
            match_time = custom.get("match_time", "")
            break
        elif event_type == "stop":
            await websocket.close()
            return

    prompt = build_booking_prompt(venue, party_size, match_time)

    try:
        async with _gemini_session_factory(prompt) as gemini:
            twilio_to_gemini = asyncio.create_task(
                _relay_twilio_to_gemini(websocket, gemini)
            )
            gemini_to_twilio = asyncio.create_task(
                _relay_gemini_to_twilio(websocket, gemini, stream_sid)
            )
            done, pending = await asyncio.wait(
                {twilio_to_gemini, gemini_to_twilio},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                exc = task.exception()
                if exc:
                    logger.error("Relay task failed: %s", exc, exc_info=exc)
            for task in pending:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
    except Exception:
        logger.exception("media_stream handler error")
    finally:
        await websocket.close()


async def _relay_twilio_to_gemini(websocket: WebSocket, gemini) -> None:
    """Read Twilio media messages and forward transcoded PCM audio to Gemini."""
    async for raw in websocket.iter_text():
        data = json.loads(raw)
        event_type = data.get("event")

        if event_type == "media":
            mulaw_bytes = base64.b64decode(data["media"]["payload"])
            pcm_bytes = mulaw_to_pcm(mulaw_bytes)
            await gemini.send(pcm_bytes)
        elif event_type == "stop":
            break


async def _relay_gemini_to_twilio(websocket: WebSocket, gemini, stream_sid: str) -> None:
    """Receive PCM audio from Gemini, transcode, and forward to Twilio.

    gemini.receive() yields chunks for a single response turn.  The outer
    loop ensures we keep listening across multiple conversational turns
    until the Twilio side disconnects or the Gemini session closes.
    """
    while True:
        async for response in gemini.receive():
            if response.data:
                mulaw_bytes = pcm_to_mulaw(response.data)
                payload = base64.b64encode(mulaw_bytes).decode()
                await websocket.send_text(json.dumps({
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": payload},
                }))

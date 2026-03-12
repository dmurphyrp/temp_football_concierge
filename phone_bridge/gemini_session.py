"""Gemini Live API session management for a single phone call.

Provides GeminiLiveSession — a thin wrapper around the google-genai SDK's
async Live API — and create_live_session, an async context manager factory
that yields a ready-to-use session.

Usage::

    async with create_live_session(system_prompt) as session:
        await session.send(pcm_16k_bytes)
        async for response in session.receive():
            if response.data:
                twilio_audio = pcm_to_mulaw(response.data)

The Live API model is set to gemini-2.5-flash, which is the current
production model for the Live API on Vertex AI.  Update _LIVE_MODEL to
switch to a newer Gemini generation when a Live API variant is available.
"""

import base64
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator

import google.genai as genai
from google.genai import types


_LIVE_MODEL = "gemini-live-2.5-flash-native-audio"
_LOCATION = "us-central1"


@dataclass
class GeminiAudioResponse:
    """Holds a single audio chunk returned by the Gemini Live session."""

    data: bytes | None = None  # PCM 16-bit 24 kHz bytes when present


class GeminiLiveSession:
    """Wraps one Gemini Live API session for bidirectional phone audio."""

    def __init__(self, raw_session) -> None:
        self._session = raw_session

    async def send(self, pcm_bytes: bytes) -> None:
        """Send a PCM 16 kHz audio chunk to Gemini.

        Args:
            pcm_bytes: Raw 16-bit little-endian PCM audio at 16 000 Hz.
        """
        await self._session.send(
            input={
                "data": base64.b64encode(pcm_bytes).decode(),
                "mime_type": "audio/pcm;rate=16000",
            },
            end_of_turn=False,
        )

    async def receive(self) -> AsyncIterator[GeminiAudioResponse]:
        """Yield PCM 24 kHz audio response chunks from Gemini.

        Yields:
            GeminiAudioResponse with .data set to raw PCM bytes when
            Gemini produces audio, or .data = None for non-audio events.
        """
        async for response in self._session.receive():
            audio_data: bytes | None = None
            server_content = getattr(response, "server_content", None)
            if server_content:
                model_turn = getattr(server_content, "model_turn", None)
                if model_turn:
                    for part in getattr(model_turn, "parts", []):
                        inline = getattr(part, "inline_data", None)
                        if inline and getattr(inline, "data", None):
                            audio_data = inline.data
            yield GeminiAudioResponse(data=audio_data)


@asynccontextmanager
async def create_live_session(system_prompt: str):
    """Async context manager yielding a GeminiLiveSession.

    Args:
        system_prompt: System instruction that tells Gemini how to behave
                       during the call (e.g. booking details and tone).

    Yields:
        A ready-to-use GeminiLiveSession.
    """
    client = genai.Client(
        vertexai=True,
        project=os.getenv("GOOGLE_CLOUD_PROJECT"),
        location=_LOCATION,
    )
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=system_prompt,
    )
    async with client.aio.live.connect(model=_LIVE_MODEL, config=config) as raw:
        yield GeminiLiveSession(raw)

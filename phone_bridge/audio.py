"""Audio format transcoding between Twilio and Gemini Live API.

Twilio streams  : G.711 mu-law, mono, 8 000 Hz, 1 byte/sample
Gemini input    : PCM 16-bit little-endian, mono, 16 000 Hz
Gemini output   : PCM 16-bit little-endian, mono, 24 000 Hz

mulaw_to_pcm  converts Twilio → Gemini input format.
pcm_to_mulaw  converts Gemini output → Twilio format.

audioop was removed in Python 3.13; audioop-lts provides it as a drop-in.
"""

import audioop


def mulaw_to_pcm(mulaw_bytes: bytes) -> bytes:
    """Convert G.711 mu-law 8 kHz audio to PCM 16-bit 16 kHz.

    Args:
        mulaw_bytes: Raw G.711 mu-law encoded audio at 8 000 Hz.

    Returns:
        Raw 16-bit little-endian PCM audio at 16 000 Hz, suitable for
        the Gemini Live API audio input.
    """
    if not mulaw_bytes:
        return b""
    # Step 1: mu-law → 16-bit linear PCM (still at 8 kHz)
    linear_8k = audioop.ulaw2lin(mulaw_bytes, 2)
    # Step 2: upsample 8 kHz → 16 kHz
    pcm_16k, _ = audioop.ratecv(linear_8k, 2, 1, 8000, 16000, None)
    return pcm_16k


def pcm_to_mulaw(pcm_bytes: bytes) -> bytes:
    """Convert PCM 16-bit 24 kHz audio to G.711 mu-law 8 kHz.

    Args:
        pcm_bytes: Raw 16-bit little-endian PCM audio at 24 000 Hz,
                   as produced by the Gemini Live API.

    Returns:
        Raw G.711 mu-law encoded audio at 8 000 Hz, suitable for
        sending back to Twilio.
    """
    if not pcm_bytes:
        return b""
    # Step 1: downsample 24 kHz → 8 kHz
    pcm_8k, _ = audioop.ratecv(pcm_bytes, 2, 1, 24000, 8000, None)
    # Step 2: 16-bit linear PCM → mu-law
    return audioop.lin2ulaw(pcm_8k, 2)

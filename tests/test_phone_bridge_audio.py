"""Tests for phone_bridge/audio.py — audio format transcoding utilities.

Twilio streams G.711 mu-law at 8 kHz.
Gemini Live API expects PCM 16-bit at 16 kHz (input)
                    and outputs PCM 16-bit at 24 kHz.

mulaw_to_pcm : G.711 mu-law 8 kHz  →  PCM 16-bit 16 kHz  (Twilio → Gemini)
pcm_to_mulaw : PCM 16-bit 24 kHz   →  G.711 mu-law 8 kHz  (Gemini → Twilio)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_concierge.phone_bridge.audio import mulaw_to_pcm, pcm_to_mulaw

# 20 ms of silence in each format:
#   8 kHz × 0.020 s × 1 byte/sample  = 160 bytes  (mu-law)
#  16 kHz × 0.020 s × 2 bytes/sample = 640 bytes  (PCM 16 kHz)
#  24 kHz × 0.020 s × 2 bytes/sample = 960 bytes  (PCM 24 kHz)
_MULAW_20MS = b"\x7f" * 160   # mu-law silence (code 0x7F ≈ PCM 0)
_PCM24_20MS = b"\x00" * 960   # PCM 24 kHz silence (all zeros)


class TestMulawToPcm:
    """mulaw_to_pcm converts G.711 mu-law 8 kHz → PCM 16-bit 16 kHz."""

    def test_returns_bytes(self):
        assert isinstance(mulaw_to_pcm(_MULAW_20MS), bytes)

    def test_empty_input_returns_empty(self):
        assert mulaw_to_pcm(b"") == b""

    def test_output_is_longer_than_input(self):
        # 8 kHz → 16 kHz doubles the sample count; 2 bytes/sample further doubles size
        assert len(mulaw_to_pcm(_MULAW_20MS)) > len(_MULAW_20MS)

    def test_output_length_reflects_upsampling(self):
        # 160 mu-law samples @8 kHz → 320 PCM samples @16 kHz × 2 bytes = 640 bytes
        result = mulaw_to_pcm(_MULAW_20MS)
        assert abs(len(result) - 640) <= 8  # allow ±1 sample for resampler rounding

    def test_different_inputs_produce_different_outputs(self):
        silence = mulaw_to_pcm(b"\x7f" * 160)
        loud = mulaw_to_pcm(b"\x00" * 160)
        assert silence != loud


class TestPcmToMulaw:
    """pcm_to_mulaw converts PCM 16-bit 24 kHz → G.711 mu-law 8 kHz."""

    def test_returns_bytes(self):
        assert isinstance(pcm_to_mulaw(_PCM24_20MS), bytes)

    def test_empty_input_returns_empty(self):
        assert pcm_to_mulaw(b"") == b""

    def test_output_is_shorter_than_input(self):
        # 24 kHz → 8 kHz reduces samples by 3×; mu-law is 1 byte vs 2 for PCM
        assert len(pcm_to_mulaw(_PCM24_20MS)) < len(_PCM24_20MS)

    def test_output_length_reflects_downsampling(self):
        # 480 PCM samples @24 kHz → 160 mu-law samples @8 kHz = 160 bytes
        result = pcm_to_mulaw(_PCM24_20MS)
        assert abs(len(result) - 160) <= 4  # allow small rounding

    def test_different_inputs_produce_different_outputs(self):
        silence = pcm_to_mulaw(b"\x00" * 960)
        loud = pcm_to_mulaw(b"\x7f\x7f" * 480)
        assert silence != loud


class TestRoundTrip:
    """Verify the two functions can be composed and test each direction's semantics.

    Note: mulaw_to_pcm outputs 16 kHz PCM (Gemini input format) and
    pcm_to_mulaw expects 24 kHz PCM (Gemini output format).  They serve
    opposite directions of the audio pipeline, so a naive roundtrip is not
    mathematically reversible.  These tests instead verify each direction's
    encoding semantics independently.
    """

    def test_mulaw_to_pcm_to_mulaw_returns_bytes(self):
        """Composing the two functions produces valid bytes without errors."""
        pcm = mulaw_to_pcm(_MULAW_20MS)
        result = pcm_to_mulaw(pcm)
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_mulaw_silence_decodes_to_near_zero_pcm(self):
        """mu-law silence (0xFF) should decode to near-zero 16-bit PCM samples."""
        import struct

        mulaw_silence = b"\xff" * 160  # 0xFF is the mu-law silence code
        pcm = mulaw_to_pcm(mulaw_silence)
        samples = struct.unpack(f"<{len(pcm) // 2}h", pcm)
        # Each sample must be very small (silence range)
        assert all(abs(s) < 500 for s in samples)

    def test_pcm_silence_encodes_to_mulaw_silence(self):
        """Linear PCM silence (all-zero bytes) must encode to mu-law silence (0xFF)."""
        pcm_silence = b"\x00" * 960  # 20 ms of silence at 24 kHz, 16-bit
        mulaw = pcm_to_mulaw(pcm_silence)
        # audioop.lin2ulaw maps 0 → 0xFF (the standard mu-law silence code)
        assert all(b == 0xFF for b in mulaw)

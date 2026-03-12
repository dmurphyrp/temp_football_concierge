"""
Pytest configuration for the event_concierge test suite.

load_secrets() is fault-tolerant: each GCP secret is fetched independently
and silently skipped when GCP credentials are absent (e.g. in CI or local
test runs).  Tests that need specific env vars supply them via
patch.dict(os.environ, ...).

Shared mock payloads and factory helpers live in helpers.py so they can
be imported normally by any test file.
"""

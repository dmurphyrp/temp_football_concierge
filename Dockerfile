# Bridge server — connects Twilio phone calls to the Gemini Live API.
# Deployed to Google Cloud Run.

FROM python:3.13-slim

WORKDIR /app

# Install only the packages needed by the bridge server.
# twilio is not required here — it is only used by the ADK agent (book_table.py).
RUN pip install --no-cache-dir \
    "fastapi>=0.110.0" \
    "uvicorn[standard]>=0.29.0" \
    "google-genai>=1.66.0" \
    "audioop-lts>=0.2.1"

# Copy the bridge module into the image.
COPY phone_bridge/ /app/phone_bridge/

# Cloud Run sets $PORT at runtime (default 8080).
ENV PORT=8080

CMD exec uvicorn phone_bridge.server:app --host 0.0.0.0 --port ${PORT}

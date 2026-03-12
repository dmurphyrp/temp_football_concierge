# Matchday Concierge

An AI agent built with [Google ADK](https://google.github.io/adk-docs/) that handles every step of planning a football matchday — finding fixtures, scouting nearby bars, booking tables, rallying friends, planning travel, and adding everything to the calendar.

---

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
  - [1. Register for a football-data.org API key](#1-register-for-a-football-dataorg-api-key)
  - [2. Set up a Google Maps API key](#2-set-up-a-google-maps-api-key)
- [Development Setup](#development-setup)
  - [3. Clone the repository](#3-clone-the-repository)
  - [4. Create a virtual environment](#4-create-a-virtual-environment)
  - [5. Install dependencies](#5-install-dependencies)
  - [6. Configure environment variables](#6-configure-environment-variables)
- [Running the Agent](#running-the-agent)
  - [7. Start the ADK web server](#7-start-the-adk-web-server)
- [Running Tests](#running-tests)
- [Agent Definition](#agent-definition)
- [Tools](#tools)
  - [get\_next\_match](#get_next_match)
  - [get\_upcoming\_matches](#get_upcoming_matches)
  - [identify\_location](#identify_location)
  - [find\_football\_bars](#find_football_bars)
  - [check\_bar\_availability](#check_bar_availability)
  - [book\_table](#book_table)
  - [notify\_friends](#notify_friends)
  - [get\_travel\_route](#get_travel_route)
  - [add\_to\_calendar](#add_to_calendar)
- [Tool Chaining](#tool-chaining)

---

## Overview

The agent is named `matchday_concierge` and runs on **Gemini 2.0 Flash** via the ADK runtime. Users interact with it through the ADK web UI (or any ADK-compatible client) to plan a matchday from scratch with a single conversational request such as:

> "When is Everton's next match? Find us a bar nearby and book a table for 6."

The agent chains tools automatically — resolving a venue from the fixture, finding nearby bars, checking availability, booking, notifying friends, planning travel, and adding the event to the calendar — without prompting the user for intermediate inputs wherever the data is already available.

---

## Project Structure

```
repos/
└── event_concierge/            # ← clone target; adk web is run from repos/
    ├── agent.py                # Root agent definition
    ├── secret_loader.py        # Loads API keys into the environment at startup
    ├── requirements.txt        # Python dependencies
    ├── .env                    # Local environment variables (not committed)
    ├── tools/
    │   ├── __init__.py         # Exports all tools
    │   ├── _football_data.py   # Shared football-data.org HTTP client
    │   ├── llm_helper_calls.py # Focused Gemini helper functions (e.g. city resolution)
    │   ├── get_next_match.py
    │   ├── get_upcoming_matches.py
    │   ├── identify_location.py
    │   ├── find_football_bars.py
    │   ├── check_bar_availability.py
    │   ├── book_table.py
    │   ├── notify_friends.py
    │   ├── get_travel_route.py
    │   └── add_to_calendar.py
    └── tests/
        ├── conftest.py
        ├── helpers.py          # Shared mock payloads
        ├── test_agent.py
        ├── test_get_next_match.py
        ├── test_get_upcoming_matches.py
        ├── test_identify_location.py
        ├── test_find_football_bars.py
        ├── test_check_bar_availability.py
        ├── test_book_table.py
        ├── test_notify_friends.py
        ├── test_get_travel_route.py
        └── test_add_to_calendar.py
```

> **Important:** `adk web` must be run from the **parent directory** of `event_concierge` (i.e. `repos/`), not from inside the project folder. See [step 7](#7-start-the-adk-web-server).

---

## Prerequisites

Before setting up the project you need two API keys. Obtain these first — you will add them to `.env` in step 6.

### 1. Register for a football-data.org API key

The agent uses the [football-data.org](https://www.football-data.org/) v4 API (free tier) to retrieve upcoming fixtures.

1. Go to [football-data.org/client/register](https://www.football-data.org/client/register)
2. Register for a free account
3. Your API key will be emailed to you and is also visible in your account dashboard
4. The free tier covers the major European leagues and international competitions with no cost

### 2. Set up a Google Maps API key

The agent uses the Google Maps **Geocoding API** and **Places Nearby API** to resolve venue locations and find nearby bars.

1. Open the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Navigate to **APIs & Services → Library** and enable:
   - **Geocoding API**
   - **Places API**
4. Navigate to **APIs & Services → Credentials** and click **Create credentials → API key**
5. Copy the generated key
6. Optionally restrict the key to the two APIs above under **API restrictions**

---

## Development Setup

### 3. Clone the repository

```bash
git clone <repo-url>
```

The folder created (e.g. `event_concierge`) will be your project root. ADK expects to be run from its **parent directory** — keep this in mind when navigating later.

### 4. Create a virtual environment

```bash
cd event_concierge
python -m venv .venv
```

Activate it:

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

### 5. Install dependencies

```bash
pip install -r requirements.txt
```

To also install test dependencies:

```bash
pip install pytest pytest-html
```

| Package | Version | Purpose |
|---------|---------|---------|
| `google-adk` | latest | ADK runtime, agent framework, Gemini model access |
| `google-cloud-secret-manager` | latest | Optional: read API keys from GCP Secret Manager in production |
| `requests` | `>=2.31.0` | HTTP client for football-data.org API calls |
| `googlemaps` | `>=4.10.0` | Google Maps Geocoding and Places Nearby APIs |
| `python-dotenv` | `>=1.0.0` | Loads `.env` into the process environment at startup |

### 6. Configure environment variables

Create a `.env` file in the `event_concierge` directory:

```bash
# from inside event_concierge/
cp .env.example .env   # or create the file manually
```

Add the two API keys obtained in the prerequisites:

```dotenv
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
FOOTBALL_DATA_API_KEY=your_football_data_api_key_here
```

`agent.py` calls `load_secrets()` at startup, which reads `.env` via `python-dotenv` and injects the values into the process environment. Any value already present in the environment (e.g. set in CI) is never overwritten.

> **Production / GCP:** As an alternative to `.env`, secrets can be stored in [GCP Secret Manager](https://cloud.google.com/secret-manager). Set `GOOGLE_CLOUD_PROJECT` to your project ID and `secret_loader.py` will pull them at startup. Each secret is fetched independently so a single missing secret does not prevent the others from loading.

---

## Running the Agent

### 7. Start the ADK web server

`adk web` must be run from the **parent directory** of `event_concierge`, not from inside the project folder. The ADK runtime discovers agents by scanning subdirectories from wherever you run the command.

```bash
# navigate to the parent of event_concierge (e.g. repos/)
cd ..

adk web
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000), select **event_concierge** from the agent dropdown, and start chatting.

Example prompts:

- `"When is Arsenal's next match?"`
- `"What football is on tonight?"`
- `"Find me a bar near Liverpool city centre to watch the match"`
- `"Book a table for 5 at The Kop Bar for the 17:30 kickoff"`
- `"Tell the Friday Footy Crew we're at The Anchor, kickoff at 15:00"`

---

## Running Tests

Run the full suite from inside `event_concierge`:

```bash
python -m pytest tests/ -v
```

Generate an HTML report:

```bash
python -m pytest tests/ -v --html=tests/report.html
```

Run a single tool's tests:

```bash
python -m pytest tests/test_get_next_match.py -v
```

All tests use mocks exclusively — no live network calls are made to any external API. No API keys are required to run the test suite.

| Test file | Covers |
|-----------|--------|
| `test_agent.py` | Agent configuration (name, model, tools list) |
| `test_get_next_match.py` | Fixture lookup, team aliases, home/away detection, API error handling |
| `test_get_upcoming_matches.py` | Time-window filtering, sorting, empty results, API errors |
| `test_identify_location.py` | Geocoding, city extraction, LLM fallback via `llm_resolve_city`, missing key, empty input |
| `test_find_football_bars.py` | Places search, rating sort, Maps links, API error states |
| `test_check_bar_availability.py` | Capacity logic, over-capacity messaging |
| `test_book_table.py` | Booking reference generation, capacity enforcement, empty venue |
| `test_notify_friends.py` | Platform validation, recipient simulation, confirmation message |
| `test_get_travel_route.py` | Departure time calculation, route structure, invalid time format |
| `test_add_to_calendar.py` | Event creation, calendar link format, 3-hour end time, invalid time |

---

## Agent Definition

**File:** `agent.py`

This is the entry point that the ADK runtime loads. It does three things:

1. **Calls `load_secrets()`** — reads API keys from `.env` (or GCP Secret Manager) and injects them into the environment before any tool runs.
2. **Imports all tools** from the `tools/` package.
3. **Defines `root_agent`** — the `Agent` instance that ADK registers and exposes in the web UI.

```python
root_agent = Agent(
    name="matchday_concierge",
    model="gemini-2.0-flash",
    description="...",
    instruction="...",
    tools=[...],
)
```

The `instruction` field is the system prompt that governs the agent's behaviour. It tells the model which tool to call in which situation, defines the automatic chaining order (fixture → location → bar search), and sets the tone of the responses. The `description` field is used by the ADK UI to label the agent in the dropdown.

The variable must be named **`root_agent`** — this is the name the ADK runtime looks for when scanning the package.

---

## Tools

### get\_next\_match

**File:** `tools/get_next_match.py`

Fetches the next scheduled fixture for a specific team over the next 14 days.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `team_name` | `str` | required | Team name (e.g. `"Arsenal"`, `"Man Utd"`, `"Everton"`) |

Common short-form aliases are resolved automatically (e.g. `"Spurs"` → `"Tottenham"`, `"Man Utd"` → `"Manchester United"`). Returns the opponent, kickoff time (UTC and human-readable), venue, competition, and whether the match is home or away.

**API:** [football-data.org v4](https://www.football-data.org/) — requires `FOOTBALL_DATA_API_KEY`.

---

### get\_upcoming\_matches

**File:** `tools/get_upcoming_matches.py`

Returns all matches kicking off across all competitions within a rolling time window.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `hours_ahead` | `int` | `24` | How many hours ahead to look (`48` for tomorrow, `72` for the weekend) |

Results are sorted by kickoff time. Useful for browsing what's on today or tonight before picking a team to follow.

**API:** [football-data.org v4](https://www.football-data.org/) — requires `FOOTBALL_DATA_API_KEY`.

> **Note:** football-data.org enforces a maximum 10-day date range per request. Both `get_next_match` and `get_upcoming_matches` automatically split larger windows into 7-day chunks to stay within this limit.

---

### identify\_location

**File:** `tools/identify_location.py`

Resolves a venue name, club name, or partial address to a normalised location string that `find_football_bars` can use directly.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `venue_text` | `str` | required | Venue, club, or stadium name extracted from a fixture (e.g. `"Arsenal FC"`, `"Goodison Park"`, `"Emirates Stadium, London"`) |

Attempts to geocode the venue text directly. If that returns no results (e.g. for a bare club name like `"Arsenal FC"`), it calls `llm_resolve_city` from `llm_helper_calls.py` to convert the name to a city, then geocodes that city instead. Returns the city/locality, full formatted address, and lat/lng coordinates. Prefers the `locality` address component (city/town) so that bar searches cover the whole surrounding area rather than just the stadium itself. Falls back to `postal_town` if no locality is present.

**APIs:** [Google Maps Geocoding API](https://developers.google.com/maps/documentation/geocoding) — requires `GOOGLE_MAPS_API_KEY`. Gemini (via `google-genai`) for LLM city resolution when direct geocoding fails.

This tool is the key link in the [automatic chaining flow](#tool-chaining).

---

### llm\_helper\_calls

**File:** `tools/llm_helper_calls.py`

Internal module containing focused, single-purpose Gemini helper functions used by other tools. Not registered as an agent tool directly.

| Function | Description |
|----------|-------------|
| `llm_resolve_city(venue_text)` | Converts a club or stadium name to its home city using Gemini (e.g. `"Arsenal FC"` → `"London"`). Returns `None` on any failure so callers degrade gracefully. |

All functions in this module return `None` on failure — missing credentials, quota errors, and network problems are all handled silently so that callers can fall back to their own error handling.

---

### find\_football\_bars

**File:** `tools/find_football_bars.py`

Searches for nearby bars and pubs using the Google Maps Places API.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `location` | `str` | required | Street address, postcode, or city name (e.g. `"Liverpool"`, `"London Bridge"`) |
| `radius_km` | `int` | `5` | Search radius in kilometres |

Geocodes the location then queries Places Nearby filtered to bars and pubs. Results are sorted by Google rating and include name, address, rating, open-now status, price level, and a direct Google Maps link.

**API:** [Google Maps Geocoding + Places Nearby](https://developers.google.com/maps/documentation/places/web-service/search-nearby) — requires `GOOGLE_MAPS_API_KEY`.

---

### check\_bar\_availability

**File:** `tools/check_bar_availability.py`

Checks whether a bar can accommodate the group for the match.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `venue_name` | `str` | required | Name of the bar or pub |
| `party_size` | `int` | required | Number of people in the group |
| `match_time` | `str` | required | ISO-8601 kickoff time (e.g. `"2026-03-14T17:30:00Z"`) |

Returns an availability flag and available seat count. Groups over 40 receive a message advising them to contact the venue directly.

> **Note:** Currently simulated. In production this would integrate with a real booking API (e.g. Google Reserve).

---

### book\_table

**File:** `tools/book_table.py`

Confirms a table reservation at the selected bar.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `venue_name` | `str` | required | Name of the bar or pub |
| `party_size` | `int` | required | Number of seats required |
| `match_time` | `str` | required | ISO-8601 kickoff time for the booking slot |

Returns a booking reference number and a confirmation message. Rejects groups over 40 with a clear error so the agent can suggest alternatives.

> **Note:** Currently simulated. In production this would integrate with a real reservation system.

---

### notify\_friends

**File:** `tools/notify_friends.py`

Sends a matchday invite to a named friend group via a messaging platform.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `message` | `str` | required | Invite text to send |
| `friend_group` | `str` | `"Friday Footy Crew"` | Name of the contact group |
| `platform` | `str` | `"WhatsApp"` | Messaging platform: `"WhatsApp"`, `"Telegram"`, or `"SMS"` |

Returns the platform used, group notified, and a simulated list of recipients.

> **Note:** Currently simulated. In production this would integrate with the respective messaging platform APIs.

---

### get\_travel\_route

**File:** `tools/get_travel_route.py`

Calculates departure times so the group arrives at the venue 30 minutes before kickoff.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `destination` | `str` | required | Address or name of the venue |
| `kickoff_time_utc` | `str` | required | ISO-8601 kickoff time in UTC |

Returns departure and arrival times for three modes — Transit, Walking, and Taxi/Uber — plus the recommended option (lowest-cost non-walking route). Includes a reminder to allow extra time on match days.

> **Note:** Journey durations are currently simulated. In production this would call the Google Maps Directions API.

---

### add\_to\_calendar

**File:** `tools/add_to_calendar.py`

Adds a matchday event to the user's Google Calendar.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `event_title` | `str` | required | Calendar event title (e.g. `"Arsenal vs Spurs – Pitch & Pint"`) |
| `start_time_utc` | `str` | required | ISO-8601 event start time in UTC |
| `location` | `str` | required | Address or name of the venue |
| `description` | `str` | `None` | Optional notes (booking ref, friends attending, etc.) |

Returns an event ID, a Google Calendar deep-link that opens the pre-filled "new event" form, and a confirmation message. End time is automatically set to 3 hours after kickoff.

---

## Tool Chaining

The agent is instructed to chain tools automatically so the user never has to provide intermediate inputs. The primary chain is:

```
get_next_match  ──┐
                  ├──► identify_location ──► find_football_bars
get_upcoming_   ──┘
matches
```

**Step-by-step:**

1. User asks for a fixture (`"When is Everton's next match?"` or `"What's on tonight?"`)
2. Agent calls `get_next_match` / `get_upcoming_matches` — the response includes a `venue` field
3. Agent **immediately** calls `identify_location(venue)` — no user prompt required
4. If `identify_location` succeeds, the agent proceeds straight to `find_football_bars(location=...)` using the resolved city name
5. If `identify_location` returns `status: not_found` or `status: error` (venue name not geocodable), the agent asks the user for a location before proceeding

**Full end-to-end chain** for a complete matchday plan:

```
get_next_match
    → identify_location
        → find_football_bars
            → check_bar_availability
                → book_table
                    → notify_friends
                    → get_travel_route
                    → add_to_calendar
```

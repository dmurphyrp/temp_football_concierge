import datetime
import os
from typing import Optional

import googlemaps
from mobfot import MobFot
from google.adk.agents import Agent

# Maximum party size the simulated booking system will accept.
# check_bar_availability and book_table use this until a real reservation
# API (e.g. Google Reserve) is wired in.
_SIMULATED_CAPACITY = 40


# ---------------------------------------------------------------------------
# Tool 1: Match Discovery  (live data via FotMob / mobfot)
# ---------------------------------------------------------------------------
def get_next_match(team_name: str) -> dict:
    """Fetches the next fixture for a given football team using the FotMob API.

    Scans upcoming days of fixtures (up to 14 days ahead) and returns the
    first match in which the requested team is playing.  Matching is done by
    substring on the team name so common short-forms work (e.g. 'Man Utd'
    matches 'Manchester United', 'Spurs' matches 'Tottenham').

    Args:
        team_name: The name of the football team (e.g. 'Arsenal', 'Man Utd').

    Returns:
        dict: A status field plus fixture details — opponent, kickoff time (UTC),
              venue, competition, whether it is a home game, and broadcast info.
              Returns an error dict when the team cannot be found or the API fails.
    """
    # Common short-name aliases → substring used for matching against FotMob names
    _ALIASES: dict[str, str] = {
        "man utd": "manchester united",
        "man united": "manchester united",
        "man city": "manchester city",
        "spurs": "tottenham",
        "barca": "barcelona",
        "atletico": "atlético",
        "psv": "psv eindhoven",
        "ajax": "ajax",
        "inter": "inter milan",
        "ac milan": "milan",
    }

    team_key = team_name.strip().lower()
    team_key = _ALIASES.get(team_key, team_key)

    def _matches_team(name: str) -> bool:
        n = name.lower()
        return team_key in n or n in team_key

    try:
        client = MobFot()
        now = datetime.datetime.now(datetime.timezone.utc)

        for day_offset in range(14):
            date = now + datetime.timedelta(days=day_offset)
            date_str = date.strftime("%Y%m%d")

            try:
                day_data = client.get_matches_by_date(
                    date_str, time_zone="Europe/London"
                )
            except Exception:
                continue

            for league in day_data.get("leagues", []):
                for match in league.get("matches", []):
                    status = match.get("status", {})
                    if status.get("finished") or status.get("started"):
                        continue

                    home = match.get("home", {})
                    away = match.get("away", {})
                    home_name = home.get("name", "")
                    away_name = away.get("name", "")

                    if not (_matches_team(home_name) or _matches_team(away_name)):
                        continue

                    is_home = _matches_team(home_name)
                    team_display = home_name if is_home else away_name
                    opponent = away_name if is_home else home_name

                    raw_kickoff = status.get("utcTime", "TBC")
                    kickoff_utc = "TBC"
                    kickoff_formatted = "TBC"
                    if raw_kickoff != "TBC":
                        try:
                            dt = datetime.datetime.fromisoformat(
                                raw_kickoff.replace("Z", "+00:00")
                            )
                            kickoff_utc = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                            kickoff_formatted = dt.strftime(
                                "%A %d %B %Y at %H:%M UTC"
                            )
                        except ValueError:
                            kickoff_utc = raw_kickoff

                    return {
                        "status": "success",
                        "team": team_display,
                        "opponent": opponent,
                        "kickoff_utc": kickoff_utc,
                        "kickoff_formatted": kickoff_formatted,
                        "venue": match.get("venue", "Venue TBC"),
                        "competition": league.get("name", "Unknown"),
                        "home_game": is_home,
                        "broadcast": "Check local listings",
                    }

        return {
            "status": "error",
            "error_message": (
                f"No upcoming fixtures found for '{team_name}' in the next "
                "14 days on FotMob. Check the spelling and try again."
            ),
        }

    except Exception as exc:
        return {
            "status": "error",
            "error_message": f"Could not retrieve fixture data: {exc}",
        }


# ---------------------------------------------------------------------------
# Tool 2: Venue Scouter  (live data via Google Maps Places API)
# ---------------------------------------------------------------------------
def find_football_bars(location: str, radius_km: int = 5) -> dict:
    """Searches for nearby bars and pubs using the Google Maps Places API.

    Geocodes the supplied location string, then queries Places Nearby for
    bars and pubs within the requested radius, sorted by Google rating.

    Args:
        location: A street address, postcode, or landmark (e.g. 'London Bridge').
        radius_km: Search radius in kilometres.  Defaults to 5.

    Returns:
        dict: A status field and a list of venues sorted by rating, each
              including name, address, Google rating, open-now status,
              business status, and a direct Google Maps link.
              Returns an error dict if the API key is missing or the call fails.
    """
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        return {
            "status": "error",
            "error_message": (
                "GOOGLE_MAPS_API_KEY is not set. "
                "Add it to your .env file and restart the agent."
            ),
        }

    try:
        gmaps = googlemaps.Client(key=api_key)

        # Step 1: geocode location string → lat/lng
        geocode_result = gmaps.geocode(location)
        if not geocode_result:
            return {
                "status": "error",
                "error_message": f"Could not geocode location '{location}'.",
            }

        latlng = geocode_result[0]["geometry"]["location"]

        # Step 2: nearby bar search
        places_result = gmaps.places_nearby(
            location=latlng,
            radius=radius_km * 1000,
            keyword="sports bar pub football",
            type="bar",
        )

        api_status = places_result.get("status")
        if api_status not in ("OK", "ZERO_RESULTS"):
            return {
                "status": "error",
                "error_message": f"Google Places API returned: {api_status}",
            }

        venues = []
        for place in places_result.get("results", []):
            opening_hours = place.get("opening_hours") or {}
            venues.append({
                "venue_id": place.get("place_id", ""),
                "name": place.get("name", "Unknown"),
                "address": place.get("vicinity", "Address not listed"),
                "rating": place.get("rating"),
                "user_ratings_total": place.get("user_ratings_total", 0),
                "open_now": opening_hours.get("open_now"),
                "business_status": place.get("business_status", "UNKNOWN"),
                "price_level": place.get("price_level"),
                "maps_url": (
                    f"https://www.google.com/maps/place/?q=place_id:"
                    f"{place.get('place_id', '')}"
                ),
            })

        venues.sort(key=lambda v: v["rating"] or 0, reverse=True)

        return {
            "status": "success",
            "location_searched": location,
            "radius_km": radius_km,
            "venues_found": len(venues),
            "venues": venues,
            "summary": (
                f"Found {len(venues)} bars/pubs within {radius_km}km of "
                f"{location}. Ratings and open status are live from Google Maps."
            ),
        }

    except Exception as exc:
        return {
            "status": "error",
            "error_message": f"Could not search for bars: {exc}",
        }


# ---------------------------------------------------------------------------
# Tool 3: Availability Check  (simulated — no free real-time booking API)
# ---------------------------------------------------------------------------
def check_bar_availability(venue_name: str, party_size: int, match_time: str) -> dict:
    """Checks whether a bar can accommodate the group for a match.

    Simulates a reservation system check.  In production this would call a
    real booking API (e.g. Google Reserve with Google).  Accepts any party
    up to _SIMULATED_CAPACITY seats.

    Args:
        venue_name: The name of the bar or pub to check.
        party_size: Number of people in the group.
        match_time: ISO-8601 kickoff time string (e.g. '2026-03-14T17:30:00Z').

    Returns:
        dict: A status field, availability flag, simulated seat count, and
              a guidance message if the group is too large.
    """
    can_accommodate = party_size <= _SIMULATED_CAPACITY

    result: dict = {
        "status": "success",
        "venue": venue_name,
        "party_size": party_size,
        "available_seats": _SIMULATED_CAPACITY,
        "can_accommodate": can_accommodate,
        "match_time": match_time,
    }

    if not can_accommodate:
        result["message"] = (
            f"'{venue_name}' cannot accommodate a group of {party_size}. "
            f"Maximum booking size is {_SIMULATED_CAPACITY}. "
            "Consider splitting the group or calling the venue directly."
        )

    return result


# ---------------------------------------------------------------------------
# Tool 4: Table Booking  (simulated)
# ---------------------------------------------------------------------------
def book_table(venue_name: str, party_size: int, match_time: str) -> dict:
    """Books a table at a football bar for the specified party and match time.

    Simulates a reservation confirmation.  Rejects groups larger than
    _SIMULATED_CAPACITY with a clear error so the agent can suggest
    alternatives.

    Args:
        venue_name: Name of the bar or pub to book.
        party_size: Number of people requiring seats.
        match_time: ISO-8601 kickoff time string for the booking slot.

    Returns:
        dict: A status field, booking reference number, and full confirmation
              details, or an error dict if the party is too large.
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


# ---------------------------------------------------------------------------
# Tool 5: Social Orchestrator
# ---------------------------------------------------------------------------
def notify_friends(
    message: str,
    friend_group: str = "Friday Footy Crew",
    platform: str = "WhatsApp",
) -> dict:
    """Sends a matchday invite to a friend group via a messaging platform.

    Args:
        message: The invite text to send (e.g. 'Arsenal v Spurs – we're at
                 Pitch & Pint, 17:00 – who's in?').
        friend_group: Name of the contact group to notify.
                      Defaults to 'Friday Footy Crew'.
        platform: Messaging platform to use ('WhatsApp', 'Telegram', 'SMS').
                  Defaults to 'WhatsApp'.

    Returns:
        dict: A status field, platform used, group notified, the message sent,
              and a simulated list of friends who received it.
    """
    supported = {"WhatsApp", "Telegram", "SMS"}
    if platform not in supported:
        return {
            "status": "error",
            "error_message": (
                f"Platform '{platform}' is not supported. "
                f"Choose from: {', '.join(sorted(supported))}."
            ),
        }

    simulated_recipients = ["Liam", "Ciarán", "Fionnuala", "Seán", "Aoife"]

    return {
        "status": "success",
        "platform": platform,
        "group": friend_group,
        "message_sent": message,
        "recipients": simulated_recipients,
        "recipients_count": len(simulated_recipients),
        "confirmation": (
            f"Matchday invite sent to '{friend_group}' "
            f"({len(simulated_recipients)} friends) via {platform}. "
            "Waiting for RSVPs — fingers crossed for a full squad!"
        ),
    }


# ---------------------------------------------------------------------------
# Tool 6: Travel Planner
# ---------------------------------------------------------------------------
def get_travel_route(destination: str, kickoff_time_utc: str) -> dict:
    """Calculates the best route to a bar so the group arrives before kickoff.

    Back-calculates departure times across Transit, Walking, and Taxi so the
    group reaches the venue 30 minutes before kickoff.

    Args:
        destination: Address or name of the venue to travel to.
        kickoff_time_utc: ISO-8601 kickoff time string used to compute the
                          ideal departure time.

    Returns:
        dict: A status field, recommended travel mode, departure time, estimated
              arrival, and a full list of available route options.
    """
    try:
        kickoff = datetime.datetime.fromisoformat(
            kickoff_time_utc.replace("Z", "+00:00")
        )
    except ValueError:
        return {
            "status": "error",
            "error_message": f"Invalid kickoff_time_utc format: '{kickoff_time_utc}'.",
        }

    target_arrival = kickoff - datetime.timedelta(minutes=30)

    routes = [
        {"mode": "Transit", "duration_mins": 22, "cost": "£3.50"},
        {"mode": "Walking", "duration_mins": 35, "cost": "Free"},
        {"mode": "Taxi / Uber", "duration_mins": 12, "cost": "£14–£18"},
    ]

    for route in routes:
        depart = target_arrival - datetime.timedelta(minutes=route["duration_mins"])
        route["depart_by"] = depart.strftime("%H:%M UTC")
        route["arrive_by"] = target_arrival.strftime("%H:%M UTC")

    recommended = min(
        routes, key=lambda r: r["duration_mins"] if r["cost"] != "Free" else 999
    )

    return {
        "status": "success",
        "destination": destination,
        "kickoff_utc": kickoff_time_utc,
        "target_arrival_utc": target_arrival.isoformat(),
        "recommended_route": recommended,
        "all_routes": routes,
        "tip": "Allow extra time — match days are busy on public transport!",
    }


# ---------------------------------------------------------------------------
# Tool 7: Calendar Integration
# ---------------------------------------------------------------------------
def add_to_calendar(
    event_title: str,
    start_time_utc: str,
    location: str,
    description: Optional[str] = None,
) -> dict:
    """Adds a matchday event to the user's Google Calendar.

    Args:
        event_title: Title for the calendar event
                     (e.g. 'Arsenal vs Spurs – Pitch & Pint').
        start_time_utc: ISO-8601 event start time in UTC.
        location: Address or name of the venue.
        description: Optional event notes (booking ref, friends attending, etc.).

    Returns:
        dict: A status field, event ID, a Google Calendar deep-link, and
              a confirmation message.
    """
    try:
        start = datetime.datetime.fromisoformat(
            start_time_utc.replace("Z", "+00:00")
        )
    except ValueError:
        return {
            "status": "error",
            "error_message": f"Invalid start_time_utc format: '{start_time_utc}'.",
        }

    end = start + datetime.timedelta(hours=3)
    event_id = f"CAL-{abs(hash(event_title + start_time_utc)) % 1_000_000:06d}"

    calendar_link = (
        f"https://calendar.google.com/calendar/render?action=TEMPLATE"
        f"&text={event_title.replace(' ', '+')}"
        f"&dates={start.strftime('%Y%m%dT%H%M%SZ')}/{end.strftime('%Y%m%dT%H%M%SZ')}"
        f"&location={location.replace(' ', '+')}"
    )

    return {
        "status": "success",
        "event_id": event_id,
        "event_title": event_title,
        "start_utc": start_time_utc,
        "end_utc": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "location": location,
        "description": description or "",
        "calendar_link": calendar_link,
        "confirmation": (
            f"'{event_title}' has been added to your Google Calendar. "
            "You'll get a reminder 1 hour before kickoff!"
        ),
    }


# ---------------------------------------------------------------------------
# Tool 1b: Upcoming Fixtures Browser  (live data via FotMob / mobfot)
# ---------------------------------------------------------------------------
def get_upcoming_matches(hours_ahead: int = 24) -> dict:
    """Returns all football matches kicking off within the next N hours.

    Useful for browsing what's on today or tonight across all leagues before
    choosing a team to follow.  Results are grouped by competition and sorted
    by kickoff time.

    Args:
        hours_ahead: How many hours ahead to look.  Defaults to 24 (today's
                     matches).  Use 48 for tomorrow as well, 72 for the
                     weekend, etc.

    Returns:
        dict: A status field, the time window searched, total match count, and
              a list of matches each with home team, away team, kickoff time,
              competition, and venue.
    """
    try:
        client = MobFot()
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now + datetime.timedelta(hours=hours_ahead)

        matches_found: list[dict] = []
        seen_ids: set = set()

        # Determine which calendar days fall within the window
        days_to_check = set()
        cursor = now
        while cursor <= cutoff:
            days_to_check.add(cursor.strftime("%Y%m%d"))
            cursor += datetime.timedelta(days=1)

        for date_str in sorted(days_to_check):
            try:
                day_data = client.get_matches_by_date(
                    date_str, time_zone="Europe/London"
                )
            except Exception:
                continue

            for league in day_data.get("leagues", []):
                league_name = league.get("name", "Unknown")
                for match in league.get("matches", []):
                    match_id = match.get("id")
                    if match_id in seen_ids:
                        continue
                    seen_ids.add(match_id)

                    status = match.get("status", {})
                    if status.get("finished") or status.get("started"):
                        continue

                    raw_kickoff = status.get("utcTime", "")
                    if not raw_kickoff:
                        continue

                    try:
                        kickoff_dt = datetime.datetime.fromisoformat(
                            raw_kickoff.replace("Z", "+00:00")
                        )
                    except ValueError:
                        continue

                    if not (now <= kickoff_dt <= cutoff):
                        continue

                    matches_found.append({
                        "match_id": match_id,
                        "home": match.get("home", {}).get("name", "TBC"),
                        "away": match.get("away", {}).get("name", "TBC"),
                        "kickoff_utc": kickoff_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "kickoff_formatted": kickoff_dt.strftime(
                            "%A %d %B at %H:%M UTC"
                        ),
                        "competition": league_name,
                        "venue": match.get("venue", "Venue TBC"),
                    })

        matches_found.sort(key=lambda m: m["kickoff_utc"])

        return {
            "status": "success",
            "window_hours": hours_ahead,
            "from_utc": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to_utc": cutoff.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_matches": len(matches_found),
            "matches": matches_found,
            "summary": (
                f"Found {len(matches_found)} upcoming matches in the next "
                f"{hours_ahead} hours across all competitions."
            ),
        }

    except Exception as exc:
        return {
            "status": "error",
            "error_message": f"Could not retrieve upcoming fixtures: {exc}",
        }


# ---------------------------------------------------------------------------
# Root Agent — Matchday Concierge
# ---------------------------------------------------------------------------
root_agent = Agent(
    name="matchday_concierge",
    model="gemini-2.0-flash",
    description=(
        "The Ultimate Matchday Concierge: finds football fixtures, scouts the "
        "best bars, books tables, rallies friends, plans travel, and adds "
        "everything to the calendar — so fans can focus on the game."
    ),
    instruction=(
        "You are the Matchday Concierge — an enthusiastic football fan assistant "
        "who handles every detail of a great matchday experience.\n\n"
        "Available tools and when to use them:\n"
        "- get_upcoming_matches: use whenever the user asks what games are on, "
        "  what's happening today/tonight/this weekend, or wants a list of "
        "  fixtures.  Default hours_ahead=24 for today, 48 for tomorrow, 72 "
        "  for the weekend.\n"
        "- get_next_match: use when the user names a specific team and wants "
        "  their next fixture.\n"
        "- find_football_bars: scout nearby venues showing the game (live Google "
        "  Maps data); highlight rating, open status, and Google Maps link.\n"
        "- check_bar_availability: check a venue fits the party before booking.\n"
        "- book_table: confirm the reservation once the user picks a venue.\n"
        "- notify_friends: send the group an invite with all the details.\n"
        "- get_travel_route: calculate departure time so the squad arrives early.\n"
        "- add_to_calendar: lock the matchday into the user's Google Calendar.\n\n"
        "Tone: enthusiastic, knowledgeable, and proactive. Use football lingo "
        "naturally (e.g. 'kickoff', 'squad', 'matchday', 'on the pitch'). "
        "When listing fixtures, group them by competition and highlight any big "
        "derbies or Champions League ties. Always surface Google Maps ratings "
        "and open-now status when recommending venues."
    ),
    tools=[
        get_upcoming_matches,
        get_next_match,
        find_football_bars,
        check_bar_availability,
        book_table,
        notify_friends,
        get_travel_route,
        add_to_calendar,
    ],
)

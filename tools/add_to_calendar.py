import datetime
from typing import Optional


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

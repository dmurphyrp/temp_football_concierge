import datetime

from ._football_data import football_data_get


def get_upcoming_matches(hours_ahead: int = 24) -> dict:
    """Returns all football matches kicking off within the next N hours.

    Useful for browsing what's on today or tonight across all leagues before
    choosing a team to follow.  Results are sorted by kickoff time.

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
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now + datetime.timedelta(hours=hours_ahead)

        # football-data.org allows a maximum 10-day window per request.
        # Chunk the full window into 7-day batches to stay within the limit.
        all_matches: list[dict] = []
        seen_ids: set = set()
        chunk_start = now
        while chunk_start < cutoff:
            chunk_end = min(chunk_start + datetime.timedelta(days=7), cutoff)
            data = football_data_get("matches", {
                "dateFrom": chunk_start.strftime("%Y-%m-%d"),
                "dateTo": (chunk_end + datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
                "status": "SCHEDULED,TIMED",
            })
            for m in data.get("matches", []):
                if m.get("id") not in seen_ids:
                    seen_ids.add(m.get("id"))
                    all_matches.append(m)
            chunk_start = chunk_end

        matches_found: list[dict] = []
        for match in all_matches:
            raw_kickoff = match.get("utcDate", "")
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

            home_team = match.get("homeTeam", {}).get("name", "TBC")
            venue = match.get("venue") or "Venue TBC"
            matches_found.append({
                "match_id": match.get("id"),
                "home": home_team,
                "away": match.get("awayTeam", {}).get("name", "TBC"),
                "kickoff_utc": kickoff_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "kickoff_formatted": kickoff_dt.strftime(
                    "%A %d %B at %H:%M UTC"
                ),
                "competition": match.get("competition", {}).get("name", "Unknown"),
                "venue": venue,
                "location_hint": venue if venue != "Venue TBC" else home_team,
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

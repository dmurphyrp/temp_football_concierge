import datetime

from ._football_data import football_data_get

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


def get_next_match(team_name: str) -> dict:
    """Fetches the next fixture for a given football team.

    Queries football-data.org for all scheduled matches in the next 14 days
    and returns the first match in which the requested team is playing.
    Matching is done by substring on the team name so common short-forms
    work (e.g. 'Man Utd' matches 'Manchester United', 'Spurs' matches
    'Tottenham').

    Args:
        team_name: The name of the football team (e.g. 'Arsenal', 'Man Utd').

    Returns:
        dict: A status field plus fixture details — opponent, kickoff time
              (UTC), venue, competition, whether it is a home game, and
              broadcast info.  Returns an error dict when the team cannot be
              found or the API fails.
    """
    team_key = team_name.strip().lower()
    team_key = _ALIASES.get(team_key, team_key)

    def _matches_team(name: str) -> bool:
        n = name.lower()
        return team_key in n or n in team_key

    try:
        now = datetime.datetime.now(datetime.timezone.utc)

        # football-data.org allows a maximum 10-day window per request.
        # Fetch two back-to-back 7-day windows to cover 14 days total.
        all_matches: list[dict] = []
        for week_offset in range(0, 14, 7):
            window_start = now + datetime.timedelta(days=week_offset)
            window_end = now + datetime.timedelta(days=week_offset + 7)
            data = football_data_get("matches", {
                "dateFrom": window_start.strftime("%Y-%m-%d"),
                "dateTo": window_end.strftime("%Y-%m-%d"),
                "status": "SCHEDULED,TIMED",
            })
            all_matches.extend(data.get("matches", []))

        for match in sorted(all_matches, key=lambda m: m.get("utcDate", "")):
            home_name = match.get("homeTeam", {}).get("name", "")
            away_name = match.get("awayTeam", {}).get("name", "")

            if not (_matches_team(home_name) or _matches_team(away_name)):
                continue

            is_home = _matches_team(home_name)
            team_display = home_name if is_home else away_name
            opponent = away_name if is_home else home_name

            raw_kickoff = match.get("utcDate", "TBC")
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

            venue = match.get("venue") or "Venue TBC"
            home_team = home_name
            return {
                "status": "success",
                "team": team_display,
                "opponent": opponent,
                "home_team": home_team,
                "kickoff_utc": kickoff_utc,
                "kickoff_formatted": kickoff_formatted,
                "venue": venue,
                "location_hint": venue if venue != "Venue TBC" else home_team,
                "competition": match.get("competition", {}).get("name", "Unknown"),
                "home_game": is_home,
                "broadcast": "Check local listings",
            }

        return {
            "status": "error",
            "error_message": (
                f"No upcoming fixtures found for '{team_name}' in the next "
                "14 days. Check the spelling and try again."
            ),
        }

    except Exception as exc:
        return {
            "status": "error",
            "error_message": f"Could not retrieve fixture data: {exc}",
        }

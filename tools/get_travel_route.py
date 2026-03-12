import datetime


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

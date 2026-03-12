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

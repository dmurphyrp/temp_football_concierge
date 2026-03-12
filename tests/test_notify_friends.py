"""Tests for tools/notify_friends.py.

This tool is pure logic with no external calls — no mocking required.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from event_concierge.tools.notify_friends import notify_friends

_MSG = "Arsenal v Spurs at Pitch & Pint, 17:30 — who's in?"


class TestNotifyFriends:
    def test_whatsapp_notification_succeeds(self):
        result = notify_friends(_MSG, platform="WhatsApp")
        assert result["status"] == "success"

    def test_telegram_notification_succeeds(self):
        result = notify_friends(_MSG, platform="Telegram")
        assert result["status"] == "success"

    def test_sms_notification_succeeds(self):
        result = notify_friends(_MSG, platform="SMS")
        assert result["status"] == "success"

    def test_unsupported_platform_returns_error(self):
        result = notify_friends(_MSG, platform="Carrier Pigeon")
        assert result["status"] == "error"
        assert "error_message" in result

    def test_message_is_echoed(self):
        result = notify_friends(_MSG)
        assert result["message_sent"] == _MSG

    def test_custom_group_is_echoed(self):
        result = notify_friends(_MSG, friend_group="Match Day Legends")
        assert result["group"] == "Match Day Legends"

    def test_default_group_is_friday_footy_crew(self):
        result = notify_friends(_MSG)
        assert result["group"] == "Friday Footy Crew"

    def test_recipients_count_is_positive(self):
        result = notify_friends(_MSG)
        assert result["recipients_count"] > 0

    def test_recipients_is_list(self):
        result = notify_friends(_MSG)
        assert isinstance(result["recipients"], list)

    def test_confirmation_mentions_platform(self):
        result = notify_friends(_MSG, platform="Telegram")
        assert "Telegram" in result["confirmation"]

    def test_confirmation_mentions_group(self):
        result = notify_friends(_MSG, friend_group="Pub Squad")
        assert "Pub Squad" in result["confirmation"]

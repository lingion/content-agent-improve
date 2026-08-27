import unittest
from datetime import datetime, timedelta, timezone
from api.aihot import AIHotError
from api.hot_radar import HotRadarError
from api.hot_topics import HotTopicsError, fetch_hot_topics

NOW = datetime(2026, 8, 25, 12, tzinfo=timezone.utc)


def payload(latest_at: str) -> dict:
    return {"items": [{"title": "topic", "latest_at": latest_at}], "canonical": "https://example.com"}


class HotTopicsFallbackTests(unittest.TestCase):
    def test_uses_fresh_aihot_without_calling_fallback(self):
        called = False
        def fallback():
            nonlocal called
            called = True
            return payload(NOW.isoformat())
        result = fetch_hot_topics(lambda: payload(NOW.isoformat()), fallback, now=NOW)
        self.assertEqual(result["provider"], "aihot")
        self.assertFalse(called)

    def test_falls_back_when_aihot_fails(self):
        def failed():
            raise AIHotError("offline")
        result = fetch_hot_topics(failed, lambda: payload(NOW.isoformat()), now=NOW)
        self.assertEqual(result["provider"], "hot-radar")

    def test_falls_back_when_aihot_is_stale(self):
        stale = (NOW - timedelta(hours=37)).isoformat()
        result = fetch_hot_topics(lambda: payload(stale), lambda: payload(NOW.isoformat()), now=NOW)
        self.assertEqual(result["provider"], "hot-radar")

    def test_falls_back_when_timestamp_is_missing(self):
        result = fetch_hot_topics(lambda: {"items": [{"title": "topic"}]}, lambda: payload(NOW.isoformat()), now=NOW)
        self.assertEqual(result["provider"], "hot-radar")

    def test_raises_when_both_fail(self):
        def failed_aihot():
            raise AIHotError("offline")
        def failed_radar():
            raise HotRadarError("offline")
        with self.assertRaises(HotTopicsError):
            fetch_hot_topics(failed_aihot, failed_radar, now=NOW)


if __name__ == "__main__":
    unittest.main()

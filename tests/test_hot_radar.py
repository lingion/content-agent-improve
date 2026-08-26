import unittest
from unittest.mock import patch
from api.hot_radar import HotRadarError, fetch_hot_radar


class HotRadarTests(unittest.TestCase):
    def test_single_source_failure_does_not_fail_collection(self):
        sources = [
            ("group", "good", lambda: [{"title": "Topic A", "hot": 10, "extra": ""}]),
            ("group", "bad", lambda: None),
        ]
        with patch("api.hot_radar.SOURCES", sources):
            result = fetch_hot_radar()
        self.assertEqual(result["provider"], "hot-radar")
        self.assertEqual(result["items"][0]["title"], "Topic A")
        self.assertEqual(result["failed_sources"][0]["source"], "bad")

    def test_all_sources_failure_raises(self):
        with patch("api.hot_radar.SOURCES", [("group", "bad", lambda: None)]):
            with self.assertRaises(HotRadarError):
                fetch_hot_radar()

    def test_respects_requested_item_limit(self):
        sources = [("group", "good", lambda: [
            {"title": f"Topic {index}", "hot": index, "extra": ""}
            for index in range(25)
        ])]
        with patch("api.hot_radar.SOURCES", sources):
            result = fetch_hot_radar(max_items=20)
        self.assertEqual(result["count"], 20)


if __name__ == "__main__":
    unittest.main()

import unittest

import requests

from api.aihot import AIHOT_AGENT_LATEST_URL, AIHotError, fetch_hot_topics


class FakeResponse:
    def __init__(self, text="", error=False):
        self.text = text
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise requests.HTTPError("upstream failed")


class AIHotTests(unittest.TestCase):
    def test_fetches_v1_hot_topics_without_credentials(self):
        captured = {}

        def fake_get(url, **kwargs):
            captured["url"] = url
            captured.update(kwargs)
            return FakeResponse(
                """# AIHOT 精选 · 过去 24 小时

1. [热点标题](https://aihot.news/items/item-1)
   OpenAI · 发布于 10-03 14:18 · 行业
   摘要：内容
   原文：https://example.com/original
"""
            )

        result = fetch_hot_topics(fake_get)

        self.assertEqual(captured["url"], AIHOT_AGENT_LATEST_URL)
        self.assertNotIn("Authorization", captured["headers"])
        self.assertNotIn("Cookie", captured["headers"])
        self.assertEqual(result["items"][0]["title"], "热点标题")
        self.assertEqual(result["items"][0]["original_url"], "https://example.com/original")
        self.assertEqual(result["items"][0]["latest_at"], "2026-10-03T06:18:00+00:00")

    def test_rejects_invalid_or_empty_payload(self):
        with self.assertRaises(AIHotError):
            fetch_hot_topics(lambda *_args, **_kwargs: FakeResponse("没有条目"))

    def test_wraps_upstream_http_failure(self):
        with self.assertRaises(AIHotError):
            fetch_hot_topics(lambda *_args, **_kwargs: FakeResponse(error=True))


if __name__ == "__main__":
    unittest.main()

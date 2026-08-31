"""Nano Researcher 热点 fallback 客户端测试。"""
import unittest
from unittest import mock

from api.nano_hot import NanoHotError, fetch_nano_hot_topics


def ok_response(payload: dict, status: int = 200):
    response = mock.Mock()
    response.status_code = status
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class NanoHotClientTests(unittest.TestCase):
    def test_parses_search_results_into_topic_items(self):
        payload = {
            "outcome": "success_with_content",
            "results": [
                {"rank": 1, "title": "今日热点A", "url": "https://example.com/a"},
                {"rank": 2, "title": "今日热点B", "url": "https://example.com/b"},
            ],
        }
        result = fetch_nano_hot_topics(http_post=lambda url, **kw: ok_response(payload))
        self.assertEqual(result["provider"], "nano-researcher")
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["items"][0]["title"], "今日热点A")
        self.assertEqual(result["items"][0]["original_url"], "https://example.com/a")
        self.assertEqual(result["items"][0]["source"], "Nano Researcher")
        self.assertIn("latest_at", result["items"][0])

    def test_raises_when_results_empty(self):
        payload = {"outcome": "success_empty", "results": []}
        with self.assertRaises(NanoHotError):
            fetch_nano_hot_topics(http_post=lambda url, **kw: ok_response(payload))

    def test_raises_on_http_error(self):
        import requests

        def post(url, **kw):
            raise requests.ConnectionError("refused")

        with self.assertRaises(NanoHotError):
            fetch_nano_hot_topics(http_post=post)

    def test_raises_on_bad_structure(self):
        with self.assertRaises(NanoHotError):
            fetch_nano_hot_topics(http_post=lambda url, **kw: ok_response({"unexpected": True}))

    def test_query_uses_env_override(self):
        seen = {}

        def post(url, **kw):
            seen["json"] = kw.get("json")
            return ok_response({"outcome": "success_with_content", "results": [
                {"title": "t", "url": "https://example.com"},
            ]})

        import os
        os.environ["NANO_HOT_QUERY"] = "科技新闻"
        try:
            fetch_nano_hot_topics(http_post=post)
        finally:
            del os.environ["NANO_HOT_QUERY"]
        self.assertEqual(seen["json"]["query"], "科技新闻")


if __name__ == "__main__":
    unittest.main()

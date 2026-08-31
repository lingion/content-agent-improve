import unittest
import tempfile
import os

import agent.publish.article_store as store


class IntegrationHelpersTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        os.chdir(self._tmp.name)

    def test_find_slug_by_article(self):
        store.build_article_dir("查找我", "wechat", "tech", "a", 8, "内容", "2026-08-30T09:00:00+08:00", topic_id=7)
        slug = store.find_slug_by_article("查找我", "wechat", "2026-08-30")
        self.assertIsNotNone(slug)
        self.assertTrue(slug.endswith("-wechat"))
        self.assertIsNone(store.find_slug_by_article("不存在的", "wechat", "2026-08-30"))

    def test_submit_article_to_library_nonblocking_failure(self):
        import unittest.mock
        with unittest.mock.patch.object(store, "push_to_articles", return_value={"ok": False, "error": "x"}):
            result = store.submit_article_to_library(
                title="后台文", platform="zhihu", direction="tech", author="a",
                score=7, content_md="正文", created_at="2026-08-30T09:00:00+08:00",
            )
        self.assertTrue(result["built"])
        self.assertFalse(result["pushed"])

    def test_submit_article_to_library_success(self):
        result = store.submit_article_to_library(
            title="成功文", platform="wechat", direction="tech", author="a",
            score=8, content_md="正文", created_at="2026-08-30T10:00:00+08:00",
        )
        self.assertTrue(result["built"])


if __name__ == "__main__":
    unittest.main()

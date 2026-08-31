import tempfile
import unittest
import os

import api.article_library as lib


class LibraryApiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._cwd = os.getcwd()
        os.chdir(self._tmp.name)
        self.addCleanup(os.chdir, self._cwd)
        lib.build_article_dir("接口文", "wechat", "tech", "a", 9, "正文内容", "2026-08-30T09:00:00+08:00")

    def test_list_endpoint(self):
        result = lib.list_library(refresh=False)
        self.assertEqual(result["articles"][0]["title"], "接口文")

    def test_detail_endpoint(self):
        rows = lib.list_library(False)["articles"]
        slug = rows[0]["slug_dir"]
        detail = lib.get_library_article(slug)
        self.assertIn("正文内容", detail["content_md"])
        self.assertEqual(detail["image_urls"], [])

    def test_detail_missing_404(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):
            lib.get_library_article("nope")

    def test_sync_endpoint(self):
        result = lib.sync_library()
        self.assertIn("push", result)
        self.assertIn("queue", result)


if __name__ == "__main__":
    unittest.main()

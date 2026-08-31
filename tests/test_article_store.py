import unittest
from agent.publish.article_store import slugify, dump_frontmatter, parse_frontmatter, FRONTMATTER_FIELDS


class SlugifyTests(unittest.TestCase):
    def test_chinese_kept(self):
        self.assertEqual(slugify("今日热点：AI 大战"), "今日热点-AI-大战")

    def test_illegal_chars_replaced(self):
        self.assertEqual(slugify("a/b\\c:d*e?f"), "a-b-c-d-e-f")

    def test_consecutive_dashes_collapsed(self):
        self.assertEqual(slugify("a---b  c"), "a-b-c")

    def test_trim_and_truncate(self):
        self.assertEqual(slugify("--hello--"), "hello")
        self.assertTrue(len(slugify("x" * 200)) <= 60)

    def test_empty_returns_untitled(self):
        self.assertEqual(slugify(""), "untitled")


class FrontmatterTests(unittest.TestCase):
    def test_dump_order_and_format(self):
        meta = {k: "" for k in FRONTMATTER_FIELDS}
        meta.update({"title": "T", "platform": "wechat", "score": 8, "topic_id": 42})
        out = dump_frontmatter(meta)
        self.assertTrue(out.startswith("---\n"))
        self.assertIn("title: T\n", out)
        self.assertIn("score: 8\n", out)
        self.assertIn("topic_id: 42\n", out)

    def test_roundtrip(self):
        meta = {"title": "标题", "platform": "zhihu", "score": 7, "topic_id": 1,
                "direction": "tech", "author": "lingion", "status": "draft",
                "wechat_media_id": "", "created_at": "2026-08-30T09:00:00+08:00",
                "published_at": ""}
        text = dump_frontmatter(meta) + "\n正文内容"
        parsed, body = parse_frontmatter(text)
        self.assertEqual(parsed["title"], "标题")
        self.assertEqual(parsed["score"], "7")
        self.assertEqual(body.strip(), "正文内容")

    def test_no_frontmatter(self):
        meta, body = parse_frontmatter("普通正文")
        self.assertEqual(meta, {})
        self.assertEqual(body, "普通正文")


if __name__ == "__main__":
    unittest.main()


import json
import tempfile
from pathlib import Path
from agent.publish.article_store import build_article_dir, parse_frontmatter, ARTICLES_DIR


class BuildArticleDirTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workspace = Path(self._tmp.name)
        import os
        self._cwd = os.getcwd()
        os.chdir(self.workspace)
        self.addCleanup(os.chdir, self._cwd)

    def _make_image(self, name: str) -> None:
        img_dir = self.workspace / "data" / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        (img_dir / name).write_bytes(b"\x89PNG fake")

    def test_builds_complete_package(self):
        self._make_image("a.png")
        content = "# 标题\n\n![配图](/api/images/a.png)\n"
        d = build_article_dir(
            title="今日热点", platform="wechat", direction="tech",
            author="lingion", score=8, content_md=content,
            created_at="2026-08-30T09:00:00+08:00", topic_id=42,
        )
        self.assertTrue((d / "article.md").exists())
        self.assertTrue((d / "meta.json").exists())
        self.assertTrue((d / "images" / "a.png").exists())
        meta, body = parse_frontmatter((d / "article.md").read_text(encoding="utf-8"))
        self.assertEqual(meta["platform"], "wechat")
        self.assertIn("images/a.png", body)
        self.assertNotIn("/api/images/", body)
        record = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "draft")

    def test_name_collision_gets_suffix(self):
        d1 = build_article_dir("同题", "wechat", "tech", "a", 7, "正文", "2026-08-30T00:00:00+08:00")
        d2 = build_article_dir("同题", "wechat", "tech", "a", 7, "正文", "2026-08-30T00:00:00+08:00")
        self.assertNotEqual(d1.name, d2.name)
        self.assertTrue(d2.name.endswith("-2"))

    def test_missing_image_not_fatal(self):
        content = "![缺失](/api/images/nope.png)"
        d = build_article_dir("t", "zhihu", "tech", "a", 7, content, "2026-08-30T00:00:00+08:00")
        self.assertTrue((d / "article.md").exists())


from agent.publish.article_store import list_articles, read_article, mark_published


class ReadLayerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        import os
        self._cwd = os.getcwd()
        os.chdir(self._tmp.name)
        self.addCleanup(os.chdir, self._cwd)

    def _build_two(self):
        build_article_dir("文章A", "wechat", "tech", "a", 8, "内容A", "2026-08-30T09:00:00+08:00")
        build_article_dir("文章B", "zhihu", "tech", "b", 7, "内容B", "2026-08-29T09:00:00+08:00")

    def test_list_sorted_desc_and_shape(self):
        self._build_two()
        rows = list_articles()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["title"], "文章A")
        self.assertIn("slug_dir", rows[0])
        self.assertIn("status", rows[0])

    def test_read_article_roundtrip(self):
        self._build_two()
        rows = list_articles()
        detail = read_article(rows[0]["slug_dir"])
        self.assertIn("内容A", detail["content_md"])
        self.assertEqual(detail["meta"]["platform"], "wechat")

    def test_read_missing_returns_none(self):
        self.assertIsNone(read_article("no-such-dir"))

    def test_mark_published_updates_both_files(self):
        self._build_two()
        rows = list_articles()
        slug = rows[0]["slug_dir"]
        self.assertTrue(mark_published(slug, media_id="media_123"))
        record = json.loads((ARTICLES_DIR / slug / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "published")
        self.assertEqual(record["wechat_media_id"], "media_123")
        meta, _ = parse_frontmatter((ARTICLES_DIR / slug / "article.md").read_text(encoding="utf-8"))
        self.assertEqual(meta["status"], "published")

    def test_mark_published_missing_returns_false(self):
        self.assertFalse(mark_published("nope"))

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

import unittest

from agent.nodes.writer import _drop_unanchored_screenshots


class ScreenshotAnchorTests(unittest.TestCase):
    def test_keeps_screenshot_whose_url_is_cited_above(self):
        draft = "\n".join([
            "据联合早报报道（https://www.zaobao.com/story-9778127），岗位激增。",
            "[SCREENSHOT: https://www.zaobao.com/story-9778127, 联合早报报道页面]",
        ])
        out, dropped = _drop_unanchored_screenshots(draft)
        self.assertEqual(dropped, 0)
        self.assertIn("[SCREENSHOT:", out)

    def test_drops_screenshot_right_after_heading(self):
        # 用例来自实测：writer 把无关页面塞在节标题后
        draft = "\n".join([
            "## 招聘数据揭示产业风向标",
            "[SCREENSHOT: https://github.com/org/agents, agents 仓库 README]",
            "正文第一段。据某来源（https://example.com/a），数据增长。",
        ])
        out, dropped = _drop_unanchored_screenshots(draft)
        self.assertEqual(dropped, 1)
        self.assertNotIn("[SCREENSHOT:", out)

    def test_drops_screenshot_whose_url_appears_nowhere_in_body(self):
        draft = "\n".join([
            "这一段没有任何引用。",
            "[SCREENSHOT: https://random-site.example/page, 某无关页面]",
        ])
        out, dropped = _drop_unanchored_screenshots(draft)
        self.assertEqual(dropped, 1)
        self.assertNotIn("[SCREENSHOT:", out)

    def test_keeps_screenshot_when_citation_is_further_up_not_adjacent(self):
        # 引用句与图之间隔了普通正文行（非标题）——仍算锚定
        draft = "\n".join([
            "据 TechOrange 报道（https://techorange.com/jpmorgan），回测获胜。",
            "补充说明一句。",
            "[SCREENSHOT: https://techorange.com/jpmorgan, TechOrange 报道页面]",
        ])
        out, dropped = _drop_unanchored_screenshots(draft)
        self.assertEqual(dropped, 0)
        self.assertIn("[SCREENSHOT:", out)

    def test_heading_adjacent_screenshot_with_citation_is_kept(self):
        # 口径更新（2026-10-09）：位置不设限，锚定是唯一标准。
        # 标题后跟一张 URL 被正文引用过的截图 → 保留
        draft = "\n".join([
            "据早报（https://zaobao.com/x）报道。",
            "## 新章节",
            "[SCREENSHOT: https://zaobao.com/x, 早报页面]",
        ])
        out, dropped = _drop_unanchored_screenshots(draft)
        self.assertEqual(dropped, 0)
        self.assertIn("[SCREENSHOT:", out)

    def test_trailing_slash_mismatch_is_tolerated(self):
        draft = "\n".join([
            "引用（https://example.com/docs/）含尾斜杠。",
            "[SCREENSHOT: https://example.com/docs, 文档页面]",
        ])
        out, dropped = _drop_unanchored_screenshots(draft)
        self.assertEqual(dropped, 0)

    def test_plain_text_without_placeholders_untouched(self):
        draft = "# 标题\n\n普通正文，无图。"
        out, dropped = _drop_unanchored_screenshots(draft)
        self.assertEqual(dropped, 0)
        self.assertEqual(out, draft)


if __name__ == "__main__":
    unittest.main()

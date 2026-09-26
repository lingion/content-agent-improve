import unittest

from agent.publish.wechat_html import md_to_wechat_html


class WeChatHtmlTests(unittest.TestCase):
    def test_plain_text_blocks_stay_light_even_with_dark_code_theme(self):
        markdown = """# 歌词示例

```text
[Intro]
Instrumental intro, clean electric guitar and soft piano
```
"""
        html = md_to_wechat_html(markdown, code_theme="atom-one-dark")["html"]
        self.assertIn("background: #f8f8f8", html.lower())
        self.assertNotIn("background: #282c34", html.lower())

    def test_default_code_theme_is_light(self):
        html = md_to_wechat_html("# 示例\n\n```text\n歌词\n```")["html"]
        self.assertIn("background: #f8f8f8", html.lower())

    def test_single_newlines_are_preserved_as_line_breaks(self):
        # 2026-09-26: 段内单换行曾被 Markdown 吞掉，叠加主题 p padding
        # 后在微信里"两行变四行"。必须显式保留为 <br>。
        html = md_to_wechat_html("# 示例\n\n第一行\n第二行")["html"]
        self.assertIn("第一行<br", html)
        self.assertIn("第二行", html)

    def test_code_blocks_wrap_long_lines(self):
        # 微信不渲染横向滚动条，长代码行会被直接裁掉。
        # pre-wrap + overflow-wrap 保证长行折行显示。
        code_line = "x" * 200
        html = md_to_wechat_html(f"# 示例\n\n```python\n{code_line}\n```")["html"]
        self.assertIn("white-space: pre-wrap", html.lower())
        self.assertIn("overflow-wrap: anywhere", html.lower())


if __name__ == "__main__":
    unittest.main()

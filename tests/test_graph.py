import unittest
from unittest.mock import patch

from agent.graph import save_memory_node, should_retry


class SaveMemoryNodeTests(unittest.TestCase):
    @patch("agent.graph.save_to_memory", side_effect=RuntimeError("embedding unavailable"))
    def test_optional_embedding_failure_does_not_fail_article(self, _save):
        result = save_memory_node(
            {
                "topic": "测试主题",
                "context": "测试素材",
                "platform": "wechat",
                "final_article": "已完成文章",
                "log": ["文章已完成"],
            }
        )

        self.assertIn("文章已正常生成", result["log"][-1])


class ScoreGateTests(unittest.TestCase):
    """质量线 >=8：8 分及以上放行，低于 8 分回炉或判失败。"""

    def test_score_9_passes(self):
        self.assertEqual(should_retry({"critic_score": 9, "retry_count": 0}), "pass")

    def test_score_10_passes(self):
        self.assertEqual(should_retry({"critic_score": 10, "retry_count": 0}), "pass")

    def test_score_8_passes(self):
        self.assertEqual(should_retry({"critic_score": 8, "retry_count": 0}), "pass")

    def test_score_7_retries(self):
        self.assertEqual(should_retry({"critic_score": 7, "retry_count": 0}), "retry")

    def test_score_8_passes_after_retry_budget(self):
        self.assertEqual(should_retry({"critic_score": 8, "retry_count": 2}), "pass")

    def test_score_5_fails_after_retry_budget(self):
        self.assertEqual(should_retry({"critic_score": 5, "retry_count": 2}), "fail")

    def test_score_7_retries_within_budget(self):
        self.assertEqual(should_retry({"critic_score": 7, "retry_count": 1}), "retry")


if __name__ == "__main__":
    unittest.main()

class ResearchHardGateTests(unittest.TestCase):
    """本轮搜索 0 素材 → 直接失败，禁止进入 Writer 写兜底稿。"""

    def test_researcher_returns_research_failed_on_zero_new_materials(self):
        from agent.nodes.researcher import researcher_node

        with (
            patch("agent.nodes.researcher._extract_keywords", return_value=["kw"]),
            patch("agent.nodes.researcher.search", return_value=[]),
        ):
            result = researcher_node({
                "topic": "测试主题",
                "platform": "wechat",
                "raw_materials": [],
                "log": [],
            })
        self.assertTrue(result["research_failed"])
        self.assertEqual(result["raw_materials"], [])
        self.assertEqual(result["context"], "")

    def test_researcher_marks_failed_even_with_stale_materials(self):
        from agent.nodes.researcher import researcher_node

        with (
            patch("agent.nodes.researcher._extract_keywords", return_value=["kw"]),
            patch("agent.nodes.researcher.search", return_value=[]),
        ):
            result = researcher_node({
                "topic": "测试主题",
                "platform": "wechat",
                "raw_materials": ["标题：旧素材\n内容：旧内容\n来源：https://example.com"],
                "log": [],
            })
        self.assertTrue(result["research_failed"])

    def test_gate_routes_fail_and_pass_correctly(self):
        from agent.graph import should_continue_after_research

        self.assertEqual(should_continue_after_research({"research_failed": True}), "fail")
        self.assertEqual(should_continue_after_research({"research_failed": False}), "pass")

class TitleEvidenceGateTests(unittest.TestCase):
    def test_title_numeric_claim_missing_from_context_is_blocked(self):
        from agent.nodes.critic import _title_evidence_violation
        self.assertIn("3.5", _title_evidence_violation(
            "主题", "来源：只有普通介绍", "# 工具在 3.5 版本新增功能\n\n正文"
        ))

    def test_title_numeric_claim_present_in_context_is_allowed(self):
        from agent.nodes.critic import _title_evidence_violation
        self.assertEqual("", _title_evidence_violation(
            "主题", "版本：3.5，来源：官方", "# 工具在 3.5 版本新增功能\n\n正文"
        ))

    def test_title_gate_ignores_unquantified_title(self):
        from agent.nodes.critic import _title_evidence_violation
        self.assertEqual("", _title_evidence_violation(
            "主题", "来源：官方介绍", "# 一个开源工具的使用方法\n\n正文"
        ))

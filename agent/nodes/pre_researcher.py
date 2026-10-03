"""
前置搜索节点 —— 在 Planner 之前执行，提供实时信息支撑规划。

职责：
  1. 基于原始 topic 执行搜索，获取实时资讯
  2. 从向量库检索历史素材（RAG）
  3. 将结果存入 state，供 Planner 参考
"""

from agent.state import AgentState
from agent.tools.search import search
from agent.memory import search_similar
import re


def _search_query(topic: str) -> str:
    """Turn a long writing brief into a focused Tavily query."""
    title = re.search(r'文章用这个标题[“\"]([^”\"]+)[”\"]', topic)
    if title:
        return title.group(1)
    urls = re.findall(r'https?://[^\s"”]+', topic)
    head = re.split(r'[。\n]', topic, maxsplit=1)[0].strip()
    return " ".join(([head[:180]] if head else []) + urls[:1])


def _full_page_text(url: str) -> str:
    """Fetch and extract the readable body for an evidence URL.
    CFP proxy first; direct fetch as fallback when proxy fails.
    """
    import requests, trafilatura
    from urllib.parse import quote
    if not url or url.startswith(("javascript:", "data:")):
        return ""
    proxy = "https://cfp.qdp.qzz.io/proxy"
    # Try CFP proxy first
    try:
        target = f"{proxy}/{quote(url, safe='')}"
        response = requests.get(target, headers={"User-Agent": "Mozilla/5.0 (content-agent research)"}, timeout=(10, 60))
        response.raise_for_status()
        text = trafilatura.extract(response.text, include_links=True, include_tables=True)
        if text and len(text) > 200:
            return text.strip()
    except Exception:
        pass
    # Direct fetch fallback
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (content-agent research)"}, timeout=(10, 60))
        response.raise_for_status()
        text = trafilatura.extract(response.text, include_links=True, include_tables=True)
        return (text or "").strip()
    except Exception:
        return ""


def pre_researcher_node(state: AgentState) -> dict:
    """基于主题做初步搜索 + RAG 检索，为 Planner 提供实时信息。"""
    topic = state["topic"]
    query = _search_query(topic)
    print(f"\n[Pre-Researcher] 预搜索：{query}")

    logs: list[str] = []
    raw_materials: list[str] = []

    # 1. 搜索实时资讯（max_results=8，加正文抓取）
    results = search(query, max_results=8)
    for r in results:
        url = r.get("url", "")
        full_text = _full_page_text(url) if url else ""
        content = full_text[:18000] if full_text else r.get("content", "")
        raw_materials.append(
            f"标题：{r.get('title', '无标题')}\n"
            f"内容：{content}\n"
            f"来源：{url}"
        )
    logs.append(f"📰 预搜索 \"{query}\" 找到 {len(results)} 条结果")
    print(f"  搜索到 {len(results)} 条结果")

    # 2. 从向量库检索历史素材
    history_items = search_similar(query, k=3)
    history_context = ""
    if history_items:
        history_context = "\n\n---\n\n".join(history_items)
        logs.append(f"📚 从素材库找到 {len(history_items)} 条历史素材")
        print(f"  📚 从素材库找到 {len(history_items)} 条历史素材")

    print(f"  预搜索完成，收集 {len(raw_materials)} 条素材")

    return {
        "raw_materials": raw_materials,
        "history_context": history_context,
        "log": state.get("log", []) + logs,
    }

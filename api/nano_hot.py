"""Nano Researcher 本地搜索服务热点适配客户端。

Nano Researcher 是查询式搜索（HTTP 原子端点 POST /v1/search），
不是榜单源：用固定热点查询词搜索，把结果标题适配成热点条目。
服务需以 RESEARCH_EXPOSE_ATOMIC_TOOLS=1 启动才开放 /v1/search。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

NANO_SEARCH_URL = "http://127.0.0.1:8787/v1/search"
DEFAULT_QUERY = "今日热点新闻 热搜榜"


class NanoHotError(RuntimeError):
    """Nano Researcher 不可用或返回结构异常。"""


def _query() -> str:
    return os.getenv("NANO_HOT_QUERY", DEFAULT_QUERY).strip() or DEFAULT_QUERY


def _parse_timestamp(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return datetime.now(timezone.utc).isoformat()


def fetch_nano_hot_topics(http_post: Callable[..., requests.Response] | None = None) -> dict[str, Any]:
    """调用 Nano /v1/search 并收敛为热点榜格式。"""
    post = http_post or requests.post
    try:
        response = post(
            NANO_SEARCH_URL,
            json={"query": _query()},
            headers={"Accept": "application/json"},
            timeout=(5, 30),
        )
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise NanoHotError("Nano Researcher 搜索服务暂时不可用") from exc

    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        raise NanoHotError("Nano Researcher 返回结构异常")

    topics: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for item in results:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        url = item.get("url")
        if not all(isinstance(value, str) and value.strip() for value in (title, url)):
            continue
        normalized = "".join(title.lower().split())
        if normalized in seen_titles:
            continue
        seen_titles.add(normalized)
        topics.append(
            {
                "id": f"nano-{len(topics) + 1}",
                "rank": len(topics) + 1,
                "title": title.strip(),
                "source": "Nano Researcher",
                "original_url": url,
                "aihot_url": url,
                "source_count": 1,
                "latest_at": _parse_timestamp(item.get("latest_at")),
            }
        )

    if not topics:
        raise NanoHotError("Nano Researcher 未返回有效结果")

    logger.info("Nano Researcher returned %d topics", len(topics))
    return {
        "count": len(topics),
        "items": topics,
        "source": "Nano Researcher",
        "provider": "nano-researcher",
        "canonical": "",
    }

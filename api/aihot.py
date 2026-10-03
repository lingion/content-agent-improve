"""AIHOT agent API 客户端。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import re
from typing import Any

import requests

AIHOT_AGENT_LATEST_URL = "https://aihot.news/api/v1/agent/latest"
AIHOT_USER_AGENT = "content-agent-improve/1.0 (+https://github.com/Benjamin202307/content-agent-improve)"
_ITEM_RE = re.compile(r"^\s*\d+\.\s+\[(?P<title>[^]]+)\]\((?P<aihot_url>https?://[^)]+)\)\s*$")
_DETAIL_RE = re.compile(r"^\s*(?P<source>[^·]+?)\s*·\s*发布于\s*(?P<published>\d{2}-\d{2}\s+\d{2}:\d{2})")
_ORIGINAL_RE = re.compile(r"^\s*原文：(?P<url>https?://\S+)\s*$")


class AIHotError(RuntimeError):
    """AIHOT 请求失败或返回 agent API 契约异常。"""


def _published_at(value: str, now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    local = datetime.strptime(f"{current.year}-{value}", "%Y-%m-%d %H:%M")
    beijing = timezone(timedelta(hours=8))
    return local.replace(tzinfo=beijing).astimezone(timezone.utc).isoformat()


def _parse_items(markdown: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in markdown.splitlines():
        match = _ITEM_RE.match(line)
        if match:
            if current and current.get("original_url"):
                items.append(current)
            current = {
                "id": match.group("aihot_url").rstrip("/").rsplit("/", 1)[-1],
                "rank": len(items) + 1,
                "title": match.group("title").strip(),
                "aihot_url": match.group("aihot_url"),
            }
            continue
        if current is None:
            continue
        detail = _DETAIL_RE.match(line)
        if detail:
            current["source"] = detail.group("source").strip()
            current["latest_at"] = _published_at(detail.group("published"))
            continue
        original = _ORIGINAL_RE.match(line)
        if original:
            current["original_url"] = original.group("url").rstrip(".,，。")
    if current and current.get("original_url"):
        items.append(current)
    return [item for item in items if item.get("title") and item.get("aihot_url") and item.get("original_url")]


def fetch_hot_topics(http_get: Callable[..., requests.Response] | None = None) -> dict[str, Any]:
    """获取 AIHOT 最近 24 小时精选，并收敛为现有热点服务格式。"""
    get = http_get or requests.get
    try:
        response = get(
            AIHOT_AGENT_LATEST_URL,
            headers={"Accept": "text/markdown", "User-Agent": AIHOT_USER_AGENT},
            timeout=(5, 20),
        )
        response.raise_for_status()
        markdown = response.text
    except (requests.RequestException, UnicodeError) as exc:
        raise AIHotError("AIHOT 热点榜暂时不可用") from exc
    topics = _parse_items(markdown)
    if not topics:
        raise AIHotError("AIHOT 热点榜返回结构异常或当前没有可用数据")
    return {"count": len(topics), "items": topics, "source": "AIHOT", "canonical": "https://aihot.news/"}

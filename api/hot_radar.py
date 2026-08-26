"""Hot Radar 多源热点采集与统一数据格式适配。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha1
import logging
from typing import Any

from api.hot_radar_sources import SOURCES

logger = logging.getLogger(__name__)


class HotRadarError(RuntimeError):
    """Hot Radar 所有数据源都不可用。"""


SOURCE_URLS = {
    "HuggingFace镜像": "https://hf-mirror.com/models", "HackerNews": "https://news.ycombinator.com/",
    "百度热搜": "https://top.baidu.com/board?tab=realtime", "IT之家": "https://www.ithome.com/",
    "uapis-微博": "https://s.weibo.com/top/summary", "uapis-知乎": "https://www.zhihu.com/hot",
    "uapis-抖音": "https://www.douyin.com/hot", "uapis-B站": "https://www.bilibili.com/v/popular/rank/all",
    "uapis-小红书": "https://www.xiaohongshu.com/explore", "GitHub本周新星": "https://github.com/trending",
    "CSDN热榜": "https://blog.csdn.net/rank/list", "dev.to": "https://dev.to/top/week",
    "贴吧": "https://tieba.baidu.com/hottopic/browse/topicList", "今日头条": "https://www.toutiao.com/hot-event/hot-board/",
    "知乎热榜": "https://www.zhihu.com/hot", "澎湃新闻": "https://www.thepaper.cn/",
    "掘金热榜": "https://juejin.cn/hot/articles", "量子位RSS": "https://www.qbitai.com/",
    "InfoQ中文": "https://www.infoq.cn/", "Solidot": "https://www.solidot.org/",
    "ProductHunt": "https://www.producthunt.com/",
}


def _collect_one(group: str, name: str, collector: Any):
    try:
        items = collector()
        return group, name, items, None if items else "empty response"
    except Exception as exc:
        return group, name, None, f"{type(exc).__name__}: {exc}"


def fetch_hot_radar(max_items: int = 10) -> dict[str, Any]:
    """并发采集 Hot Radar 数据源，并适配成前端现有热点格式。"""
    successful = []
    failed: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=12, thread_name_prefix="hot-radar") as executor:
        futures = {executor.submit(_collect_one, group, name, fn): index for index, (group, name, fn) in enumerate(SOURCES)}
        for future in as_completed(futures):
            index = futures[future]
            group, name, items, error = future.result()
            if items:
                successful.append((index, group, name, items))
            else:
                failed.append({"source": name, "error": error or "unknown error"})
    if not successful:
        logger.error("Hot Radar failed: all %d sources unavailable", len(SOURCES))
        raise HotRadarError("Hot Radar 所有数据源均不可用")

    topics = []
    seen_titles: set[str] = set()
    collected_at = datetime.now(timezone.utc).isoformat()
    ordered_sources = sorted(successful)
    # 轮询取各源条目，避免前 10 条全被第一个数据源占满。
    max_source_items = max(len(items) for _, _, _, items in ordered_sources)
    for item_index in range(max_source_items):
        for _, _group, source_name, items in ordered_sources:
            if item_index >= len(items):
                continue
            item = items[item_index]
            source_url = SOURCE_URLS.get(source_name, "")
            title = str(item.get("title", "")).strip()
            normalized = "".join(title.lower().split())
            if not title or title == "?" or normalized in seen_titles:
                continue
            seen_titles.add(normalized)
            topics.append({
                "id": f"hot-radar-{sha1((source_name + title).encode()).hexdigest()[:16]}",
                "rank": len(topics) + 1, "title": title, "source": source_name,
                "original_url": source_url, "aihot_url": source_url, "source_count": 1,
                "latest_at": collected_at, "hot": item.get("hot", ""), "extra": item.get("extra", ""),
            })
            if len(topics) >= max_items:
                break
        if len(topics) >= max_items:
            break
    if not topics:
        raise HotRadarError("Hot Radar 未返回有效热点")
    logger.info("Hot Radar collected %d topics from %d/%d sources; failed_sources=%s", len(topics), len(successful), len(SOURCES), [x["source"] for x in failed])
    return {"count": len(topics), "items": topics, "source": "Hot Radar", "provider": "hot-radar", "canonical": "", "failed_sources": failed}

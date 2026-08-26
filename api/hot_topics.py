"""AIHot 优先、Hot Radar 兜底的统一热点服务。"""

from __future__ import annotations
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
import logging
import os
from typing import Any
from api.aihot import AIHotError, fetch_hot_topics as fetch_aihot
from api.hot_radar import fetch_hot_radar

logger = logging.getLogger(__name__)
DEFAULT_MAX_AGE_HOURS = 36.0


class HotTopicsError(RuntimeError):
    """所有热点提供方均不可用。"""


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validate_aihot_freshness(payload: dict[str, Any], now: datetime, max_age_hours: float) -> None:
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise AIHotError("AIHot 热点榜当前没有可用数据")
    timestamps = [stamp for item in items if isinstance(item, dict) if (stamp := _parse_timestamp(item.get("latest_at")))]
    if not timestamps:
        raise AIHotError("AIHot 热点缺少可验证的更新时间")
    if max(timestamps) < now.astimezone(timezone.utc) - timedelta(hours=max_age_hours):
        raise AIHotError(f"AIHot 热点数据已超过 {max_age_hours:g} 小时未更新")


def fetch_hot_topics(aihot_fetcher: Callable[[], dict[str, Any]] = fetch_aihot, hot_radar_fetcher: Callable[[], dict[str, Any]] = fetch_hot_radar, *, now: datetime | None = None, max_age_hours: float | None = None) -> dict[str, Any]:
    """优先返回 AIHot；失败、空数据或过期时自动使用 Hot Radar。"""
    current_time = now or datetime.now(timezone.utc)
    if max_age_hours is None:
        try:
            max_age_hours = float(os.getenv("HOT_TOPICS_MAX_AGE_HOURS", DEFAULT_MAX_AGE_HOURS))
        except ValueError:
            logger.warning("Invalid HOT_TOPICS_MAX_AGE_HOURS; using default %s", DEFAULT_MAX_AGE_HOURS)
            max_age_hours = DEFAULT_MAX_AGE_HOURS
    try:
        result = aihot_fetcher()
        _validate_aihot_freshness(result, current_time, max_age_hours)
        result["provider"] = "aihot"
        result.setdefault("failed_sources", [])
        logger.info("Hot topics provider selected: aihot; count=%d", len(result["items"]))
        return result
    except Exception as exc:
        logger.warning("AIHot unavailable, falling back to Hot Radar: %s", exc)
    try:
        result = hot_radar_fetcher()
        result["provider"] = "hot-radar"
        logger.info("Hot topics provider selected: hot-radar; count=%d", len(result.get("items", [])))
        return result
    except Exception as exc:
        logger.error("Both hot topic providers failed: %s", exc)
        raise HotTopicsError("AIHot 与 Hot Radar 热点服务均暂时不可用") from exc

"""团队文章库浏览 API。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from agent.publish.article_store import (
    build_article_dir,  # noqa: F401  (re-export 供测试)
    list_articles,
    read_article,
    push_to_articles,
    retry_push_queue,
)

router = APIRouter(prefix="/api/library", tags=["library"])


@router.get("")
def list_library(refresh: bool = False) -> dict:
    return {"articles": list_articles(refresh=refresh)}


@router.get("/{slug}")
def get_library_article(slug: str) -> dict:
    detail = read_article(slug)
    if detail is None:
        raise HTTPException(status_code=404, detail="文章不存在")
    detail["image_urls"] = [
        f"/api/library-files/{slug}/images/{name}" for name in detail.pop("images", [])
    ]
    return detail


@router.post("/sync")
def sync_library() -> dict:
    return {"push": push_to_articles(), "queue": retry_push_queue()}

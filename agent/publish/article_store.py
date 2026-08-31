"""团队文章库：articles/ 目录的构建、读写与 git 推送。"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

FRONTMATTER_FIELDS = [
    "title", "topic_id", "platform", "direction", "author", "score",
    "status", "wechat_media_id", "created_at", "published_at",
]

ARTICLES_DIR = Path("articles")
IMAGE_REF_PATTERN = re.compile(r"/api/images/([\w.\-]+)")
CST = timezone(timedelta(hours=8))


def slugify(text: str, max_len: int = 60) -> str:
    text = re.sub(r"[^\w一-鿿-]+", "-", text.strip())
    text = re.sub(r"-{2,}", "-", text).strip("-")
    text = text[:max_len].rstrip("-")
    return text or "untitled"


def dump_frontmatter(meta: dict) -> str:
    lines = ["---"]
    for key in FRONTMATTER_FIELDS:
        lines.append(f"{key}: {meta.get(key, '')}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    meta = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, text[end + 4:].lstrip("\n")


def rewrite_image_paths(content_md: str) -> str:
    return IMAGE_REF_PATTERN.sub(r"images/\1", content_md)


def build_article_dir(
    title: str,
    platform: str,
    direction: str,
    author: str,
    score: int,
    content_md: str,
    created_at: str,
    topic_id: int = 0,
    source_images_dir: Path | None = None,
) -> Path:
    """构建完整可发布包目录：article.md + images/ + meta.json。"""
    day = created_at[:10] if len(created_at) >= 10 else datetime.now(CST).strftime("%Y-%m-%d")
    base = f"{day}-{slugify(title)}-{platform}"
    target = ARTICLES_DIR / base
    if target.exists():
        index = 2
        while (ARTICLES_DIR / f"{base}-{index}").exists():
            index += 1
        target = ARTICLES_DIR / f"{base}-{index}"

    images_out = target / "images"
    images_out.mkdir(parents=True, exist_ok=True)

    rewritten = rewrite_image_paths(content_md)
    meta = {
        "title": title,
        "topic_id": topic_id,
        "platform": platform,
        "direction": direction,
        "author": author,
        "score": score,
        "status": "draft",
        "wechat_media_id": "",
        "created_at": created_at,
        "published_at": "",
    }
    (target / "article.md").write_text(dump_frontmatter(meta) + "\n" + rewritten, encoding="utf-8")

    src_dir = Path(source_images_dir) if source_images_dir else Path("data/images")
    for match in IMAGE_REF_PATTERN.finditer(content_md):
        src = src_dir / match.group(1)
        if src.exists():
            shutil.copy2(src, images_out / match.group(1))

    record = dict(meta)
    record["slug_dir"] = target.name
    (target / "meta.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return target


def _git_pull() -> bool:
    """静默 pull，失败（无网络/无仓库）不影响本地浏览。"""
    try:
        subprocess.run(
            ["git", "pull", "--rebase", "origin", "main"],
            capture_output=True, timeout=60, check=True,
        )
        return True
    except Exception:
        return False


def list_articles(refresh: bool = False) -> list[dict]:
    if refresh:
        _git_pull()
    rows = []
    if not ARTICLES_DIR.exists():
        return rows
    for meta_file in sorted(ARTICLES_DIR.glob("*/meta.json")):
        try:
            record = json.loads(meta_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        rows.append(record)
    rows.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
    return rows


def read_article(slug_dir: str) -> dict | None:
    target = ARTICLES_DIR / slug_dir
    article = target / "article.md"
    if not article.exists():
        return None
    meta, body = parse_frontmatter(article.read_text(encoding="utf-8"))
    images_dir = target / "images"
    images = sorted(p.name for p in images_dir.glob("*") if p.is_file()) if images_dir.exists() else []
    return {"meta": meta, "content_md": body, "images": images}


def mark_published(slug_dir: str, media_id: str = "") -> bool:
    target = ARTICLES_DIR / slug_dir
    article = target / "article.md"
    meta_file = target / "meta.json"
    if not article.exists() or not meta_file.exists():
        return False
    meta, body = parse_frontmatter(article.read_text(encoding="utf-8"))
    meta.update({
        "status": "published",
        "published_at": datetime.now(CST).isoformat(),
        "wechat_media_id": media_id,
    })
    article.write_text(dump_frontmatter(meta) + "\n" + body, encoding="utf-8")
    try:
        record = json.loads(meta_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        record = {}
    record.update({k: meta[k] for k in ("status", "published_at", "wechat_media_id")})
    meta_file.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return True

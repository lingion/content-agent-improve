"""团队文章库：articles/ 目录的构建、读写与 git 推送。"""

from __future__ import annotations

import re
from pathlib import Path

FRONTMATTER_FIELDS = [
    "title", "topic_id", "platform", "direction", "author", "score",
    "status", "wechat_media_id", "created_at", "published_at",
]

ARTICLES_DIR = Path("articles")


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

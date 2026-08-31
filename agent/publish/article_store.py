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


PUSH_QUEUE_PATH = Path("data/push_queue.json")


def get_push_token() -> str | None:
    import os as _os
    token = _os.getenv("ARTICLE_REPO_TOKEN", "").strip()
    if token:
        return token
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
        token = out.stdout.strip()
        return token or None
    except Exception:
        return None


def _enqueue(message: str) -> None:
    PUSH_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        queue = json.loads(PUSH_QUEUE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        queue = []
    if message not in queue:
        queue.append(message)
    PUSH_QUEUE_PATH.write_text(json.dumps(queue, ensure_ascii=False), encoding="utf-8")


def _run_git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, timeout=120)


def push_to_articles(commit_message: str | None = None) -> dict:
    """提交并推送 articles/ 变更。无变更直接成功。失败入队待重试。"""
    if not ARTICLES_DIR.exists():
        return {"ok": True, "error": ""}
    status = _run_git("status", "--porcelain", "--", str(ARTICLES_DIR))
    if status.returncode != 0:
        _enqueue(commit_message or "feat: article library sync")
        return {"ok": False, "error": f"git status failed: {status.stderr.strip()}"}
    if not status.stdout.strip():
        return {"ok": True, "error": ""}

    message = commit_message or f"feat: article library sync ({datetime.now(CST).strftime('%Y-%m-%d %H:%M')})"
    add = _run_git("add", str(ARTICLES_DIR))
    commit = _run_git("commit", "-m", message)
    if commit.returncode != 0:
        _enqueue(message)
        return {"ok": False, "error": f"git commit failed: {commit.stderr.strip()}"}

    if get_push_token() is None:
        _enqueue(message)
        return {"ok": False, "error": "未配置推送凭证（ARTICLE_REPO_TOKEN 或 gh auth token）"}

    pull = _run_git("pull", "--rebase", "origin", "main")
    if pull.returncode != 0:
        _run_git("rebase", "--abort")
        _enqueue(message)
        return {"ok": False, "error": f"git pull --rebase failed: {pull.stderr.strip()}"}

    push = _run_git("push", "origin", "main")
    if push.returncode != 0:
        _enqueue(message)
        return {"ok": False, "error": f"git push failed: {push.stderr.strip()}"}
    return {"ok": True, "error": ""}


def retry_push_queue() -> dict:
    try:
        queue = json.loads(PUSH_QUEUE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        queue = []
    if not queue:
        return {"ok": True, "error": "", "retried": 0}
    for message in list(queue):
        result = push_to_articles(message)
        if not result["ok"]:
            return {"ok": False, "error": result["error"], "retried": queue.index(message)}
        queue.remove(message)
    PUSH_QUEUE_PATH.write_text(json.dumps(queue, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "error": "", "retried": len(queue)}


def find_slug_by_article(topic_title: str, platform: str, created_at_prefix: str) -> str | None:
    """按 title+platform+日期前缀在 articles 索引中找 slug_dir。"""
    for row in list_articles():
        if row.get("title") == topic_title and row.get("platform") == platform \
                and str(row.get("created_at", "")).startswith(created_at_prefix):
            return row.get("slug_dir")
    return None


def submit_article_to_library(
    title: str, platform: str, direction: str, author: str,
    score: int, content_md: str, created_at: str, topic_id: int = 0,
    push: bool = True,
) -> dict:
    """入库 + 尽力推送。任何失败都不抛异常，返回执行报告。"""
    report = {"built": False, "slug_dir": "", "pushed": False, "error": ""}
    try:
        target = build_article_dir(title, platform, direction, author, score, content_md, created_at, topic_id)
        report["built"] = True
        report["slug_dir"] = target.name
        if push:
            result = push_to_articles(f"feat: article {target.name} by {author}")
            report["pushed"] = result["ok"]
            if not result["ok"]:
                report["error"] = result["error"]
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    return report

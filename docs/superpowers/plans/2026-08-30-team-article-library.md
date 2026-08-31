# 团队文章库 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成的文章自动以"完整可发布包"形态推送到项目仓库 `articles/` 目录，几十人共享浏览、可直接拿来发布。

**Architecture:** 纯函数层 `article_store.py`（目录构建/frontmatter/push）+ FastAPI router（浏览/同步 API）+ 生成与发布流程挂钩 + 前端 LibraryPanel 页签。推送走本机 git（token 从 `ARTICLE_REPO_TOKEN` 或 `gh auth token`），失败进本地队列不阻塞。

**Tech Stack:** Python 3.12 / FastAPI / unittest / git CLI / Next.js + Ant Design

## Global Constraints

- 测试框架：unittest（`uv run` 不可用，用 `.venv/bin/python -m unittest`）
- 全部新代码中文注释禁用 emoji（用户全局规则：✓✗⚠★ 允许）
- 遵循现有风格：api/ 下模块级函数、tests/ 下 unittest.TestCase
- frontmatter 解析不引第三方库，手写最小 YAML 子集解析（key: value 行格式）
- 不修改 DB schema
- commit 用 conventional commits（feat:/test:/fix:）

---

### Task 1: frontmatter 序列化与 slug 化（纯函数）

**Files:**
- Create: `agent/publish/article_store.py`
- Test: `tests/test_article_store.py`

**Interfaces:**
- Produces:
  - `slugify(text: str, max_len: int = 60) -> str`（URL 安全 slug，中文转拼音不需要——保留中文，替换路径非法字符为 `-`，合并连续 `-`，trim `-`，超长截断）
  - `dump_frontmatter(meta: dict) -> str`（按 spec 字段顺序输出 `---\nkey: value\n---\n`）
  - `parse_frontmatter(text: str) -> tuple[dict, str]`（返回 (meta, 正文)；无 frontmatter 返回 ({}, 原文)）
  - `FRONTMATTER_FIELDS: list[str]`（字段顺序：title, topic_id, platform, direction, author, score, status, wechat_media_id, created_at, published_at）

- [ ] **Step 1: 写失败测试**

```python
import unittest
from agent.publish.article_store import slugify, dump_frontmatter, parse_frontmatter, FRONTMATTER_FIELDS


class SlugifyTests(unittest.TestCase):
    def test_chinese_kept(self):
        self.assertEqual(slugify("今日热点：AI 大战"), "今日热点-AI-大战")

    def test_illegal_chars_replaced(self):
        self.assertEqual(slugify("a/b\\c:d*e?f"), "a-b-c-d-e-f")

    def test_consecutive_dashes_collapsed(self):
        self.assertEqual(slugify("a---b  c"), "a-b-c")

    def test_trim_and_truncate(self):
        self.assertEqual(slugify("--hello--"), "hello")
        self.assertTrue(len(slugify("x" * 200)) <= 60)

    def test_empty_returnsUntitled(self):
        self.assertEqual(slugify(""), "untitled")


class FrontmatterTests(unittest.TestCase):
    def test_dump_order_and_format(self):
        meta = {k: "" for k in FRONTMATTER_FIELDS}
        meta.update({"title": "T", "platform": "wechat", "score": 8, "topic_id": 42})
        out = dump_frontmatter(meta)
        self.assertTrue(out.startswith("---\n"))
        self.assertIn("title: T\n", out)
        self.assertIn("score: 8\n", out)
        self.assertIn("topic_id: 42\n", out)

    def test_roundtrip(self):
        meta = {"title": "标题", "platform": "zhihu", "score": 7, "topic_id": 1,
                "direction": "tech", "author": "lingion", "status": "draft",
                "wechat_media_id": "", "created_at": "2026-08-30T09:00:00+08:00",
                "published_at": ""}
        text = dump_frontmatter(meta) + "\n正文内容"
        parsed, body = parse_frontmatter(text)
        self.assertEqual(parsed["title"], "标题")
        self.assertEqual(parsed["score"], "7")  # 全部按字符串解析
        self.assertEqual(body.strip(), "正文内容")

    def test_no_frontmatter(self):
        meta, body = parse_frontmatter("普通正文")
        self.assertEqual(meta, {})
        self.assertEqual(body, "普通正文")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd ~/src/content-agent-improve && .venv/bin/python -m unittest tests.test_article_store 2>&1 | tail -3`
Expected: FAIL / ImportError（模块不存在）

- [ ] **Step 3: 最小实现**

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m unittest tests.test_article_store 2>&1 | tail -3`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add agent/publish/article_store.py tests/test_article_store.py
git commit -m "feat: article_store frontmatter serialization and slugify"
```

---

### Task 2: build_article_dir 目录构建

**Files:**
- Modify: `agent/publish/article_store.py`
- Test: `tests/test_article_store.py`（追加）

**Interfaces:**
- Consumes: Task 1 的 `slugify/dump_frontmatter/parse_frontmatter/ARTICLES_DIR`
- Produces:
  - `build_article_dir(title: str, platform: str, direction: str, author: str, score: int, content_md: str, created_at: str, topic_id: int = 0, source_images_dir: Path | None = None) -> Path`
    行为：`ARTICLES_DIR/<YYYY-MM-DD>-<slug>-<platform>/` 下写 `article.md`（frontmatter + 正文，正文里 `/api/images/<name>` 重写为 `images/<name>`）、拷贝 `source_images_dir`（默认 `data/images`）中被正文引用的图片到 `images/`、写 `meta.json`（元数据 + `slug_dir` 目录名）。返回目录 Path。目录已存在时追加 `-2`。
  - `rewrite_image_paths(content_md: str) -> str`

- [ ] **Step 1: 追加失败测试**

```python
import json
import tempfile
from pathlib import Path
from agent.publish.article_store import build_article_dir, parse_frontmatter, ARTICLES_DIR


class BuildArticleDirTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workspace = Path(self._tmp.name)
        # 在临时目录里跑，不污染真实 articles/
        import os
        self._cwd = os.getcwd()
        os.chdir(self.workspace)
        self.addCleanup(os.chdir, self._cwd)

    def _make_image(self, name: str) -> None:
        img_dir = self.workspace / "data" / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        (img_dir / name).write_bytes(b"\x89PNG fake")

    def test_builds_complete_package(self):
        self._make_image("a.png")
        content = "# 标题\n\n![配图](/api/images/a.png)\n"
        d = build_article_dir(
            title="今日热点", platform="wechat", direction="tech",
            author="lingion", score=8, content_md=content,
            created_at="2026-08-30T09:00:00+08:00", topic_id=42,
        )
        self.assertTrue((d / "article.md").exists())
        self.assertTrue((d / "meta.json").exists())
        self.assertTrue((d / "images" / "a.png").exists())
        meta, body = parse_frontmatter((d / "article.md").read_text(encoding="utf-8"))
        self.assertEqual(meta["platform"], "wechat")
        self.assertIn("images/a.png", body)
        self.assertNotIn("/api/images/", body)
        record = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "draft")

    def test_name_collision_gets_suffix(self):
        d1 = build_article_dir("同题", "wechat", "tech", "a", 7, "正文", "2026-08-30T00:00:00+08:00")
        d2 = build_article_dir("同题", "wechat", "tech", "a", 7, "正文", "2026-08-30T00:00:00+08:00")
        self.assertNotEqual(d1.name, d2.name)
        self.assertTrue(d2.name.endswith("-2"))

    def test_missing_image_not_fatal(self):
        content = "![缺失](/api/images/nope.png)"
        d = build_article_dir("t", "zhihu", "tech", "a", 7, content, "2026-08-30T00:00:00+08:00")
        self.assertTrue((d / "article.md").exists())
```

- [ ] **Step 2: 跑测试确认新用例失败**

Run: `.venv/bin/python -m unittest tests.test_article_store 2>&1 | tail -3`
Expected: FAIL（build_article_dir 未定义）

- [ ] **Step 3: 实现**

在 `article_store.py` 追加：

```python
import json
import shutil
from datetime import datetime, timezone, timedelta

IMAGE_REF_PATTERN = re.compile(r"/api/images/([\w.\-]+)")
CST = timezone(timedelta(hours=8))


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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m unittest tests.test_article_store 2>&1 | tail -3`
Expected: OK（全部用例）

- [ ] **Step 5: Commit**

```bash
git add agent/publish/article_store.py tests/test_article_store.py
git commit -m "feat: build complete publishable article package directory"
```

---

### Task 3: list / read / mark_published 读取层

**Files:**
- Modify: `agent/publish/article_store.py`
- Test: `tests/test_article_store.py`（追加）

**Interfaces:**
- Consumes: Task 2 的 build 产物结构
- Produces:
  - `list_articles(refresh: bool = False) -> list[dict]`（refresh=True 先 `git pull`（静默失败忽略）；扫 `articles/*/meta.json`，按 created_at 倒序）
  - `read_article(slug_dir: str) -> dict | None`（返回 `{"meta": dict含正文frontmatter, "content_md": str, "images": list[str]}`；不存在返回 None）
  - `mark_published(slug_dir: str, media_id: str = "") -> bool`（更新 meta.json + article.md frontmatter 的 status/published_at/wechat_media_id；目录不存在返回 False）

- [ ] **Step 1: 追加失败测试**

```python
from agent.publish.article_store import list_articles, read_article, mark_published


class ReadLayerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        import os
        self._cwd = os.getcwd()
        os.chdir(self._tmp.name)
        self.addCleanup(os.chdir, self._cwd)

    def _build_two(self):
        build_article_dir("文章A", "wechat", "tech", "a", 8, "内容A", "2026-08-30T09:00:00+08:00")
        build_article_dir("文章B", "zhihu", "tech", "b", 7, "内容B", "2026-08-29T09:00:00+08:00")

    def test_list_sorted_desc_and_shape(self):
        self._build_two()
        rows = list_articles()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["title"], "文章A")  # 新的在前
        self.assertIn("slug_dir", rows[0])
        self.assertIn("status", rows[0])

    def test_read_article_roundtrip(self):
        self._build_two()
        rows = list_articles()
        detail = read_article(rows[0]["slug_dir"])
        self.assertIn("内容A", detail["content_md"])
        self.assertEqual(detail["meta"]["platform"], "wechat")

    def test_read_missing_returns_none(self):
        self.assertIsNone(read_article("no-such-dir"))

    def test_mark_published_updates_both_files(self):
        self._build_two()
        rows = list_articles()
        slug = rows[0]["slug_dir"]
        self.assertTrue(mark_published(slug, media_id="media_123"))
        record = json.loads((ARTICLES_DIR / slug / "meta.json").read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "published")
        self.assertEqual(record["wechat_media_id"], "media_123")
        meta, _ = parse_frontmatter((ARTICLES_DIR / slug / "article.md").read_text(encoding="utf-8"))
        self.assertEqual(meta["status"], "published")

    def test_mark_published_missing_returns_false(self):
        self.assertFalse(mark_published("nope"))
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m unittest tests.test_article_store 2>&1 | tail -3`
Expected: FAIL

- [ ] **Step 3: 实现**

```python
import subprocess


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
    images = sorted(p.name for p in (target / "images").glob("*") if p.is_file()) if (target / "images").exists() else []
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m unittest tests.test_article_store 2>&1 | tail -3`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add agent/publish/article_store.py tests/test_article_store.py
git commit -m "feat: article library list/read/mark-published"
```

---

### Task 4: push 推送层 + 失败队列

**Files:**
- Modify: `agent/publish/article_store.py`
- Test: `tests/test_article_push.py`（新文件，用 local bare repo 当远端，不碰网络）

**Interfaces:**
- Consumes: Task 1-3 全部
- Produces:
  - `get_push_token() -> str | None`（`ARTICLE_REPO_TOKEN` env → `gh auth token` 输出 → None）
  - `push_to_articles(commit_message: str | None = None) -> dict`（返回 `{"ok": bool, "error": str}`；有新变更时 `git add articles/ && commit && pull --rebase && push`；无变更返回 ok；rebase 冲突 → `rebase --abort` 后返回错误并写入 `data/push_queue.json`）
  - `retry_push_queue() -> dict`（逐条重试队列中的 commit message，全部成功后清空队列）
  - `PUSH_QUEUE_PATH = Path("data/push_queue.json")`

- [ ] **Step 1: 写失败测试**

```python
"""push 层测试：用本地 bare repo 当 origin，不发网络请求。"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import agent.publish.article_store as store


class PushTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.workspace = Path(self._tmp.name) / "work"
        self.workspace.mkdir()
        self.bare = Path(self._tmp.name) / "remote.git"

        def git(*args, cwd=None):
            subprocess.run(["git", *args], cwd=cwd or self.workspace,
                           capture_output=True, check=True)

        git("init", "--bare", str(self.bare))
        git("init")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        git("checkout", "-b", "main")
        (self.workspace / "README.md").write_text("x")
        git("add", ".")
        git("commit", "-m", "init")
        git("remote", "add", "origin", str(self.bare))
        git("push", "-u", "origin", "main")

        import os
        self._cwd = os.getcwd()
        os.chdir(self.workspace)
        self.addCleanup(os.chdir, self._cwd)
        # 清掉可能的环境凭证干扰
        self._env_patch = unittest.mock.patch.dict("os.environ", {"ARTICLE_REPO_TOKEN": ""}, clear=False)
        self._env_patch.start()
        self.addCleanup(self._env_patch.stop)

    import unittest.mock

    def test_push_creates_commit_with_articles(self):
        store.build_article_dir("推送文", "wechat", "tech", "a", 8, "内容", "2026-08-30T09:00:00+08:00")
        result = store.push_to_articles("feat: add 推送文")
        self.assertTrue(result["ok"], result.get("error", ""))
        log = subprocess.run(["git", "log", "--oneline", "-2"], cwd=self.workspace,
                             capture_output=True, text=True).stdout
        self.assertIn("推送文", log)

    def test_push_no_changes_is_ok(self):
        result = store.push_to_articles()
        self.assertTrue(result["ok"])

    def test_failure_enqueues_message(self):
        with unittest.mock.patch.object(store.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "git")):
            result = store.push_to_articles("feat: broken")
        self.assertFalse(result["ok"])
        queue = json.loads(store.PUSH_QUEUE_PATH.read_text(encoding="utf-8"))
        self.assertIn("feat: broken", queue)

    def test_retry_queue_drains(self):
        store.PUSH_QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
        store.PUSH_QUEUE_PATH.write_text(json.dumps(["feat: queued"]), encoding="utf-8")
        result = store.retry_push_queue()
        self.assertTrue(result["ok"])
        self.assertEqual(json.loads(store.PUSH_QUEUE_PATH.read_text(encoding="utf-8")), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m unittest tests.test_article_push 2>&1 | tail -3`
Expected: FAIL（函数不存在）

- [ ] **Step 3: 实现**

```python
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
        error = f"git status failed: {status.stderr.strip()}"
        _enqueue(commit_message or "feat: article library sync")
        return {"ok": False, "error": error}
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m unittest tests.test_article_push tests.test_article_store 2>&1 | tail -3`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add agent/publish/article_store.py tests/test_article_push.py
git commit -m "feat: git push layer with offline retry queue"
```

---

### Task 5: FastAPI router（浏览/详情/同步）

**Files:**
- Create: `api/article_library.py`
- Modify: `api/server.py`（import + include + 静态挂载）
- Test: `tests/test_article_library_api.py`

**Interfaces:**
- Consumes: Task 3-4 的 `list_articles/read_article/mark_published/push_to_articles/retry_push_queue`
- Produces:
  - `router: APIRouter`，路由：
    - `GET /api/library?refresh=0` → `{"articles": [...]}`
    - `GET /api/library/{slug}` → `{"meta", "content_md", "image_urls": ["/api/library-files/<slug>/images/<name>"]}`，404 当不存在
    - `POST /api/library/sync` → push + retry queue 结果 `{"push": {...}, "queue": {...}}`

- [ ] **Step 1: 写失败测试**

```python
import json
import tempfile
import unittest
from fastapi.testclient import TestClient

import api.article_library as lib


class LibraryApiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        import os
        self._cwd = os.getcwd()
        os.chdir(self._tmp.name)
        self.addCleanup(os.chdir, self._cwd)
        lib.build_article_dir("接口文", "wechat", "tech", "a", 9, "正文内容", "2026-08-30T09:00:00+08:00")
        self.client = TestClient(lib.router)

    def test_list_endpoint(self):
        # TestClient 直接挂 router 需要 app；改用完整 app 的方式在 server 集成测。
        # 这里直接调用 route 函数。
        result = lib.list_library(refresh=False)
        self.assertEqual(result["articles"][0]["title"], "接口文")

    def test_detail_endpoint(self):
        rows = lib.list_library(False)["articles"]
        slug = rows[0]["slug_dir"]
        detail = lib.get_library_article(slug)
        self.assertIn("正文内容", detail["content_md"])
        self.assertTrue(detail["image_urls"] == [] or detail["image_urls"][0].startswith("/api/library-files/"))

    def test_sync_endpoint(self):
        result = lib.sync_library()
        self.assertIn("push", result)
        self.assertIn("queue", result)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m unittest tests.test_article_library_api 2>&1 | tail -3`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

`api/article_library.py`：

```python
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
```

`api/server.py` 两处改动（在热点榜 import 附近加）：

```python
from api.article_library import router as article_library_router
```

在 `app = FastAPI(...)` 与静态挂载区（`app.mount("/api/images"...)` 附近）加：

```python
app.include_router(article_library_router)
app.mount("/api/library-files", StaticFiles(directory="articles"), name="library-files")
```

并在文件尾部 `os.makedirs("data/images", exist_ok=True)` 附近加：

```python
os.makedirs("articles", exist_ok=True)
```

- [ ] **Step 4: 跑测试确认通过 + server 可 import**

Run: `.venv/bin/python -m unittest tests.test_article_library_api 2>&1 | tail -3 && .venv/bin/python -c "import api.server"`
Expected: OK + 无输出

- [ ] **Step 5: Commit**

```bash
git add api/article_library.py api/server.py tests/test_article_library_api.py
git commit -m "feat: article library browse API and static mount"
```

---

### Task 6: 生成流程自动入库 + 发布回写

**Files:**
- Modify: `api/server.py`（generate SSE 尾部 + wechat_publish）
- Modify: `agent/publish/article_store.py`（加 `find_slug_by_article` 辅助）
- Test: `tests/test_server_library_integration.py`

**Interfaces:**
- Consumes: Task 2 `build_article_dir`、Task 4 `push_to_articles`；server 现有 `db.create_article` 返回 dict、`last_state`（含 topic/direction/score/final_article）
- Produces:
  - `find_slug_by_article(topic_title: str, platform: str, created_at_prefix: str) -> str | None`（按 title+platform+日期前缀在 meta 索引中查）
  - generate 流程：文章存 DB 后，后台线程入库+push（`ARTICLE_LIBRARY_ENABLED != "0"` 时启用）
  - wechat_publish：`article_id` 且发布成功 → 查找 slug → `mark_published` → push

- [ ] **Step 1: 写失败测试**

```python
import unittest
import tempfile, os
from pathlib import Path

import agent.publish.article_store as store


class IntegrationHelpersTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        os.chdir(self._tmp.name)

    def test_find_slug_by_article(self):
        store.build_article_dir("查找我", "wechat", "tech", "a", 8, "内容", "2026-08-30T09:00:00+08:00", topic_id=7)
        slug = store.find_slug_by_article("查找我", "wechat", "2026-08-30")
        self.assertIsNotNone(slug)
        self.assertTrue(slug.endswith("-wechat"))
        self.assertIsNone(store.find_slug_by_article("不存在的", "wechat", "2026-08-30"))

    def test_background_submit_nonblocking_failure(self):
        # push 失败不抛异常
        with unittest.mock.patch.object(store, "push_to_articles", return_value={"ok": False, "error": "x"}):
            result = store.submit_article_to_library(
                title="后台文", platform="zhihu", direction="tech", author="a",
                score=7, content_md="正文", created_at="2026-08-30T09:00:00+08:00",
            )
        self.assertTrue(result["built"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m unittest tests.test_server_library_integration 2>&1 | tail -3`
Expected: FAIL（find_slug_by_article / submit_article_to_library 不存在）

- [ ] **Step 3: 实现辅助函数（article_store.py 追加）**

```python
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m unittest tests.test_server_library_integration 2>&1 | tail -3`
Expected: OK

- [ ] **Step 5: server.py 生成流程挂钩（wechat_publish 回写）**

在 `api/server.py` 的 generate SSE 中，`article_record` 写 DB 成功的代码块之后追加：

```python
        # 团队文章库：后台线程入库+推送，不阻塞 SSE 结束
        if article_record and os.getenv("ARTICLE_LIBRARY_ENABLED", "1") != "0":
            import threading
            from agent.publish.article_store import submit_article_to_library

            def _push_library():
                report = submit_article_to_library(
                    title=req.topic[:120], platform=req.platform,
                    direction=req.direction, author=os.getenv("ARTICLE_AUTHOR", ""),
                    score=score, content_md=article_md,
                    created_at=datetime.now(timezone(timedelta(hours=8))).isoformat(),
                    topic_id=topic_id,
                )
                print(f"[Library] 推送结果：{report}")

            threading.Thread(target=_push_library, daemon=True).start()
```

在 `wechat_publish` 成功分支（`db.update_article(article_id, status="published", ...)` 之后）追加：

```python
            # 团队文章库状态回写
            from agent.publish.article_store import find_slug_by_article, mark_published, push_to_articles
            try:
                slug = find_slug_by_article("", "wechat", datetime.now().strftime("%Y-%m-%d"))
                # 注：wechat_publish 只有 md_text 无 topic 标题；slug 查找走 article_id 关联：
                if article_id:
                    art = db.get_article(article_id)
                    if art:
                        topic_rec = db.get_topic(art["topic_id"])
                        if topic_rec:
                            slug = find_slug_by_article(
                                topic_rec["title"][:120], "wechat",
                                datetime.fromtimestamp(art["created_at"] / 1000).strftime("%Y-%m-%d"),
                            )
                if slug and mark_published(slug, media_id=result.get("media_id", "")):
                    push_to_articles(f"feat: publish article {slug}")
            except Exception as exc:
                print(f"[Library] 发布状态回写失败（不影响发布）：{exc}")
```

注意：`created_at` 是 epoch **秒**（`agent/db.py:120` `int(time.time())` 已核实），回写查找用 `datetime.fromtimestamp(art["created_at"]).strftime(...)`，不要除以 1000。另外 topic 标题可能带规划文案后缀，find 用 `topic_rec["title"][:120]` 与入库时一致。

- [ ] **Step 6: server import 冒烟**

Run: `.venv/bin/python -c "import api.server"`
Expected: 无输出

- [ ] **Step 7: 全量回归**

Run: `.venv/bin/python -m unittest discover tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: OK，无回归

- [ ] **Step 8: Commit**

```bash
git add api/server.py agent/publish/article_store.py tests/test_server_library_integration.py
git commit -m "feat: auto-push generated articles to team library and writeback publish status"
```

---

### Task 7: 前端「团队文章库」页签

**Files:**
- Create: `web/app/components/LibraryPanel.tsx`
- Modify: `web/app/page.tsx`（加页签切换）
- Modify: `web/app/types/` 或新建 `web/app/types/library.ts`（类型）

**Interfaces:**
- Consumes: Task 5 的 `GET /api/library`、`GET /api/library/{slug}`、`POST /api/library/sync`、`/api/library-files/*` 静态图
- Produces: `<LibraryPanel />` 组件，页签入口

- [ ] **Step 1: 类型定义**

```typescript
// web/app/types/library.ts
export interface LibraryArticle {
  slug_dir: string;
  title: string;
  platform: string;
  direction: string;
  author: string;
  score: number | string;
  status: string;
  created_at: string;
  published_at?: string;
}

export interface LibraryDetail {
  meta: Partial<LibraryArticle>;
  content_md: string;
  image_urls: string[];
}
```

- [ ] **Step 2: LibraryPanel 组件**

```tsx
// web/app/components/LibraryPanel.tsx
'use client';

import { useCallback, useEffect, useState } from 'react';
import { List, Tag, Button, Space, Typography, Spin, Empty, message, Modal } from 'antd';
import { ReloadOutlined, CopyOutlined } from '@ant-design/icons';
import type { LibraryArticle, LibraryDetail } from '../types/library';
import PlatformIcons from './PlatformIcons';

const { Text } = Typography;

export default function LibraryPanel() {
  const [articles, setArticles] = useState<LibraryArticle[]>([]);
  const [loading, setLoading] = useState(false);
  const [detail, setDetail] = useState<LibraryDetail | null>(null);

  const load = useCallback(async (refresh = false) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/library?refresh=${refresh ? 1 : 0}`);
      const data = await res.json();
      setArticles(data.articles ?? []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openDetail = async (slug: string) => {
    const res = await fetch(`/api/library/${encodeURIComponent(slug)}`);
    if (res.ok) setDetail(await res.json());
  };

  const copyBody = async () => {
    if (!detail) return;
    await navigator.clipboard.writeText(detail.content_md);
    message.success('正文已复制');
  };

  return (
    <div style={{ padding: 16 }}>
      <Space style={{ marginBottom: 12 }}>
        <Button icon={<ReloadOutlined />} onClick={() => load(true)} loading={loading}>刷新（拉取远端）</Button>
      </Space>
      <Spin spinning={loading}>
        {articles.length === 0 ? (
          <Empty description="文章库为空" />
        ) : (
          <List
            dataSource={articles}
            renderItem={(item) => (
              <List.Item
                style={{ cursor: 'pointer' }}
                onClick={() => openDetail(item.slug_dir)}
                actions={[
                  <Tag key="status" color={item.status === 'published' ? 'green' : 'orange'}>
                    {item.status === 'published' ? '已发布' : '草稿'}
                  </Tag>,
                ]}
              >
                <List.Item.Meta
                  title={<Space>{PlatformIcons[item.platform] ?? item.platform}{item.title}</Space>}
                  description={
                    <Space split="·">
                      <Text type="secondary">{item.author || '未知作者'}</Text>
                      <Text type="secondary">{(item.created_at || '').slice(0, 10)}</Text>
                      <Text type="secondary">评分 {item.score}</Text>
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </Spin>

      <Modal
        open={!!detail}
        title={detail?.meta?.title}
        width={820}
        footer={[
          <Button key="copy" icon={<CopyOutlined />} onClick={copyBody}>复制正文</Button>,
        ]}
        onCancel={() => setDetail(null)}
      >
        <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>{detail?.content_md}</pre>
      </Modal>
    </div>
  );
}
```

注意：`PlatformIcons` 的实际导出形态需先读 `web/app/components/PlatformIcons.tsx` 对齐（可能是组件或映射表），以上为占位用法，实现时以真实导出为准。正文渲染先用 `pre` 直出（MVP），Markdown 渲染后续可复用 ArticlePanel 的渲染器。

- [ ] **Step 3: page.tsx 页签集成**

读 `web/app/page.tsx` 现有布局（三栏），在顶部加一个受控 `Tabs` 或轻量按钮组切换「创作台 / 团队文章库」两个视图。实现时以现有布局结构为准，最小侵入：

```tsx
const [view, setView] = useState<'create' | 'library'>('create');
// 顶部加：
// <Tabs activeKey={view} onChange={(k) => setView(k as any)} items={[
//   { key: 'create', label: '创作台' },
//   { key: 'library', label: '团队文章库' },
// ]} />
// view === 'library' 时渲染 <LibraryPanel />，否则渲染原三栏
```

- [ ] **Step 4: 前端构建验证**

Run: `cd web && bun run build 2>&1 | tail -5`
Expected: 构建成功无类型错误

- [ ] **Step 5: 浏览器手工验证（后端起服务）**

```bash
cd ~/src/content-agent-improve && .venv/bin/python -m uvicorn api.server:app --port 8917 &
cd web && bun dev
# 浏览器 http://localhost:3917
```

验证：页签切换正常；文章库空态显示；手工 `git apply` 一篇假文章目录后刷新列表出现；详情弹窗正文与图片显示；复制按钮生效。

- [ ] **Step 6: Commit**

```bash
git add web/app/components/LibraryPanel.tsx web/app/page.tsx web/app/types/library.ts
git commit -m "feat: team article library tab in web UI"
```

---

### Task 8: 文档 + 全量回归收尾

**Files:**
- Modify: `README.md`（功能清单加一条 + 环境变量说明）
- Modify: `CLAUDE.md`（开发约定加文章库一行）

- [ ] **Step 1: README 补充**

在「功能 → 文章管理」小节后加：

```markdown
**团队文章库**
- 生成完的文章自动打包（正文+配图+元数据）推送到本仓库 `articles/` 目录，全团队共享
- Web 端「团队文章库」页签浏览，可直接复制正文去发布
- 发布微信公众号后自动回写"已发布"状态
- 推送凭证：环境变量 `ARTICLE_REPO_TOKEN`（或本机 `gh auth token`）；`ARTICLE_LIBRARY_ENABLED=0` 关闭自动推送；`ARTICLE_AUTHOR` 标注作者名
```

- [ ] **Step 2: 全量回归**

Run: `.venv/bin/python -m unittest discover tests 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: team article library usage and env vars"
```

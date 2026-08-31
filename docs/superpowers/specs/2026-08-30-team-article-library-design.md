# 团队文章库（Team Article Library）设计

日期：2026-08-30
状态：已确认

## 背景与目标

公司几十人使用 content-agent 生成文章。需要共享文章库：每人生成完的文章自动推送到项目仓库 `articles/` 文件夹，所有人拉取/在线浏览，看到别人做了什么、可直接拿来发布。不做重复判断，人工自查。

## 已确认决策

- 规模：几十人，Git 同步方案（无中央服务）
- 去重：不做，人工自己看
- 文章形态：完整可发布包（正文 + 配图 + 元数据）
- 交付：直接改 content-agent-improve 本身，含 web 前端
- 仓库：推到本项目自己的仓库 `articles/` 目录
- 认证：每人本机 `gh auth token` 优先，环境变量 `ARTICLE_REPO_TOKEN` 兜底
- 自动 push：生成完自动推；发布微信后再推一次更新状态
- 图片：存仓库内（Git 存图，规模可承受）

## 文章目录格式

```
articles/
  2026-08-30-<slug>-wechat/        ← slug 来自主题标题（URL 安全化，60 字符内）
    article.md                      ← YAML frontmatter + 正文
    images/
      <原文件名>                     ← 从 data/images/ 拷贝
    meta.json                       ← 机器可读元数据（与 frontmatter 冗余，前端列表用）
```

frontmatter 字段（`article.md` 头部，`---` 包裹）：

| 字段 | 类型 | 说明 |
|---|---|---|
| title | str | 文章标题（topic 截取） |
| topic_id | int | 本地 DB topic id（各人本地不同，仅参考） |
| platform | str | wechat / xiaohongshu / zhihu |
| direction | str | 内容方向（tech/finance/...） |
| author | str | GitHub 用户名或本地用户名 |
| score | int | critic 评分 |
| status | str | draft / published |
| wechat_media_id | str | 发布后回填 |
| created_at | ISO8601 | 生成时间 |
| published_at | ISO8601 | 发布时间（未发布为空） |

正文中的本地图片引用 `/api/images/xxx.png` 在推送时重写为相对路径 `images/xxx.png`。

## 组件

### 1. `agent/publish/article_store.py`（新建）

纯函数层，无 FastAPI 依赖：

- `build_article_dir(title, platform, direction, author, score, content_md, created_at, topic_id) -> Path`
  在 `articles/` 下创建目录，写 `article.md`（frontmatter+正文，重写图片路径）、拷贝图片、写 `meta.json`。返回目录路径。
- `push_to_articles(commit_message) -> {ok, error}`
  `git add articles/ && git commit && git pull --rebase && git push`。token 来源：`ARTICLE_REPO_TOKEN` env → `gh auth token`。pull --rebase 冲突时自动重试一次。
- `list_articles() -> list[dict]`：扫 `articles/*/meta.json`（先 `git pull`），返回按 created_at 倒序的列表。
- `read_article(slug_dir) -> {meta, content_md}`：读单篇。
- `mark_published(slug_dir, media_id) -> {ok}`：改 status/published_at/wechat_media_id，重写 meta.json + frontmatter，push。

### 2. `api/article_library.py`（新建，FastAPI router）

- `GET /api/library` → list（含可选 `?refresh=1` 强制 pull）
- `GET /api/library/{slug}` → 单篇详情（正文 + 图片列表）
- 图片服务：复用现有静态挂载方式，新增 mount `articles/` → `/api/library-files`（只读）
- `POST /api/library/sync` → 手动触发 push 待推队列

### 3. 生成流程集成（改 `api/server.py` generate SSE 尾部）

文章入库 DB 后，若 `ARTICLE_LIBRARY_ENABLED`（默认开）：
后台线程调 `build_article_dir` + `push_to_articles`。失败不阻塞 SSE 正常结束，结果记录 log 并落 `data/push_queue.json` 待重试。

### 4. 发布状态回写（改 `api/server.py` wechat_publish）

发布成功且该文章有对应 articles 目录（按 topic_id+platform 在 meta 索引中查）→ `mark_published` push。

### 5. web 前端「团队文章库」页签

- 新组件 `web/app/components/LibraryPanel.tsx`：
  - 列表视图：标题 / 作者 / 平台图标 / 日期 / 状态徽标（draft/published）
  - 详情视图：Markdown 渲染正文（复用 ArticlePanel 渲染逻辑），图片走 `/api/library-files`
  - 操作：复制正文、复制微信 HTML（复用 publish preview 接口）、下载
- 主页加页签切换（现有三栏布局中加 tab，风格与现有一致）

## 推送认证

```
ARTICLE_REPO_TOKEN 环境变量（首选）
→ gh auth token（本机 gh CLI 已登录）
→ 都没有：本地保留，进 push 队列，前端显示"未配置推送凭证"
```

远端固定用 origin（即项目仓库）。push 前先 `git pull --rebase origin main`。

## 错误处理

| 场景 | 行为 |
|---|---|
| push 网络/权限失败 | 入 `data/push_queue.json`，下次生成/手动 sync 重试，不影响本地产物 |
| rebase 冲突 | 用 `git rebase --abort` 回退，整目录换个 slug 重试一次（目录名加 `-2`） |
| 图片缺失 | 目录照建，图片目录可能不完整，不阻塞 |
| gh/token 都无 | 同 push 失败路径，UI 提示 |

## 测试

- 单测（unittest，仿现有 tests/ 风格）：
  - frontmatter 序列化/解析 round-trip
  - slug 化（中文、特殊字符、超长）
  - build_article_dir：目录结构、图片拷贝、路径重写
  - mark_published 状态回写
  - push 失败入队、队列重试（mock git 命令）
- 不做真实网络 push 测试（本地 git bare repo 做 push 目标验证）

## Not Doing

- 不做去重/查重（用户明确人工自查）
- 不做权限分级（Git 仓库权限即权限）
- 不做评论/点赞等协作功能
- 不做全文搜索（目录浏览够用，后续可加）
- 不改 DB schema（articles 目录自足，DB 仍是本地索引）

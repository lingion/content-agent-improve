#!/usr/bin/env python3
"""
hot-radar collect.py — 一次性拉取全部核心热榜源
纯标准库,无第三方依赖。任何Python 3.7+环境直接跑。
输出: stdout人类可读报告 + 可选 --json 输出结构化JSON
"""
import json
import sys
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import date, timedelta

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
TIMEOUT = 8

def fetch_json(url, headers=None, data=None, method=None):
    """GET/POST返回解析后的JSON。失败返回None。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    if data is not None:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
    if method:
        req.method = method
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception:
        return None

def fetch_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None

# ---------- 源采集器(每个返回 list[dict] 或 None) ----------

def src_huggingface(limit=10):
    """HF镜像 trending models — AI趋势锚点"""
    d = fetch_json(f"https://hf-mirror.com/api/models?sort=trendingScore&direction=-1&limit={limit}")
    if not isinstance(d, list) or not d:
        return None
    return [{
        "title": m.get("id", "?"),
        "hot": m.get("trendingScore", "?"),
        "extra": f"dl={m.get('downloads','?')} likes={m.get('likes','?')}",
    } for m in d]

def src_hn(limit=10):
    """HN Algolia front page"""
    d = fetch_json(f"https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage={limit}")
    hits = (d or {}).get("hits", [])
    if not hits:
        return None
    return [{
        "title": h.get("title", "?"),
        "hot": h.get("points", "?"),
        "extra": f"comments={h.get('num_comments','?')}",
    } for h in hits]

def src_baidu(limit=10):
    """百度热搜 — 必须platform=pc。content结构在单层/双层嵌套间漂移,两种都兼容"""
    d = fetch_json("https://top.baidu.com/api/board?platform=pc&tab=realtime")
    try:
        content = d["data"]["cards"][0]["content"]
        # 双层形态: content[0]是dict且含'content'键
        if content and isinstance(content[0], dict) and "content" in content[0]:
            content = content[0]["content"]
        return [{
            "title": i.get("word", "?"),
            "hot": i.get("hotScore", "?"),
            "extra": "",
        } for i in content[:limit]]
    except (TypeError, KeyError, IndexError):
        return None

def src_ithome(limit=10):
    """IT之家 — hitcount/commentcount"""
    d = fetch_json("https://api.ithome.com/json/newslist/news?r=0")
    items = (d or {}).get("newslist", [])
    if not items:
        return None
    return [{
        "title": i.get("title", "?"),
        "hot": i.get("hitcount", "?"),
        "extra": f"comments={i.get('commentcount','?')}",
    } for i in items[:limit]]

def src_uapis(platform="weibo", limit=10):
    """uapis.cn 多平台聚合"""
    d = fetch_json(f"https://uapis.cn/api/v1/misc/hotboard?type={platform}")
    items = (d or {}).get("list", []) if isinstance(d, dict) else None
    if not items:
        return None
    return [{
        "title": i.get("title", "?"),
        "hot": i.get("hot_value", "?"),
        "extra": "",
    } for i in items[:limit]]

def src_github(limit=10):
    """GitHub 本周新建高star repo — 增量趋势"""
    since = (date.today() - timedelta(days=7)).isoformat()
    d = fetch_json(f"https://api.github.com/search/repositories?q=created:>{since}+stars:>100&sort=stars&order=desc&per_page={limit}")
    items = (d or {}).get("items", [])
    if not items:
        return None
    return [{
        "title": i.get("full_name", "?"),
        "hot": i.get("stargazers_count", "?"),
        "extra": (i.get("description") or "")[:40],
    } for i in items]

def src_csdn(limit=10):
    """CSDN热榜"""
    d = fetch_json("https://blog.csdn.net/phoenix/web/blog/hot-rank?page=0&pageSize={}&childType=hot".format(limit))
    items = (d or {}).get("data", [])
    if not items:
        return None
    return [{
        "title": i.get("articleTitle", "?"),
        "hot": i.get("hotRankScore", "?"),
        "extra": i.get("nickName", ""),
    } for i in items]

def src_devto(limit=10):
    """dev.to top articles"""
    d = fetch_json(f"https://dev.to/api/articles?top=7&per_page={limit}")
    if not isinstance(d, list) or not d:
        return None
    return [{
        "title": a.get("title", "?"),
        "hot": a.get("positive_reactions_count", "?"),
        "extra": f"comments={a.get('comments_count','?')}",
    } for a in d]

def src_tieba(limit=10):
    """贴吧热搜 — bang_topic是dict,条目在topic_list"""
    d = fetch_json("https://tieba.baidu.com/hottopic/browse/topicList?ie=utf-8")
    try:
        items = d["data"]["bang_topic"]["topic_list"]
        return [{
            "title": i.get("topic_name", "?"),
            "hot": i.get("discuss_num", "?"),
            "extra": "",
        } for i in items[:limit]]
    except (TypeError, KeyError):
        return None

def src_toutiao(limit=10):
    """今日头条热榜 — 只有标题"""
    d = fetch_json("https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc")
    items = (d or {}).get("data", [])
    if not items:
        return None
    return [{
        "title": i.get("Title", "?"),
        "hot": "",
        "extra": "",
    } for i in items[:limit]]

def src_zhihu(limit=10):
    """知乎热榜 — detail_text含'512 万热度',hot值优于知乎日报(title-only)"""
    d = fetch_json("https://api.zhihu.com/topstory/hot-list?limit={}".format(limit))
    items = (d or {}).get("data", [])
    if not items:
        return None
    return [{
        "title": (i.get("target") or {}).get("title", "?"),
        "hot": i.get("detail_text", ""),
        "extra": "",
    } for i in items]

def src_paper(limit=10):
    """澎湃hotNews"""
    d = fetch_json("https://cache.thepaper.cn/contentapi/wwwIndex/rightSidebar")
    try:
        items = d["data"]["hotNews"]
        return [{
            "title": i.get("name", "?"),
            "hot": "",
            "extra": "",
        } for i in items[:limit]]
    except (TypeError, KeyError):
        return None

def src_juejin(limit=10):
    """掘金热榜 — POST, title在item_info.article_info"""
    d = fetch_json(
        "https://api.juejin.cn/recommend_api/v1/article/recommend_all_feed",
        data={"id_type": 2, "client_type": 2608, "sort_type": 200, "cursor": "0", "limit": limit},
        method="POST",
    )
    items = (d or {}).get("data", [])
    if not items:
        return None
    out = []
    for i in items:
        try:
            out.append({"title": i["item_info"]["article_info"]["title"], "hot": "", "extra": ""})
        except (TypeError, KeyError):
            continue
    return out or None

def src_rss(url, limit=10, atom=False):
    """通用RSS/Atom解析"""
    text = fetch_text(url)
    if not text:
        return None
    try:
        root = ET.fromstring(text)
        if atom:
            ns = {"a": "http://www.w3.org/2005/Atom"}
            entries = root.findall("a:entry", ns)
            titles = [e.find("a:title", ns).text for e in entries if e.find("a:title", ns) is not None]
        else:
            items = root.findall(".//item")
            titles = [i.find("title").text for i in items if i.find("title") is not None]
        if not titles:
            return None
        return [{"title": t, "hot": "", "extra": ""} for t in titles[:limit]]
    except ET.ParseError:
        return None

# ---------- 编排 ----------

SOURCES = [
    # (组名, 源名, 采集函数)
    ("🥇 T1 AI趋势", "HuggingFace镜像", src_huggingface),
    ("🥇 T1 AI趋势", "HackerNews", src_hn),
    ("🥇 T1 国内", "百度热搜", src_baidu),
    ("🥇 T1 国内", "IT之家", src_ithome),
    ("🥇 T1 国内", "uapis-微博", lambda: src_uapis("weibo")),
    ("🥇 T1 国内", "uapis-知乎", lambda: src_uapis("zhihu")),
    ("🥇 T1 国内", "uapis-抖音", lambda: src_uapis("douyin")),
    ("🥇 T1 国内", "uapis-B站", lambda: src_uapis("bilibili")),
    ("🥇 T1 国内", "uapis-小红书", lambda: src_uapis("xiaohongshu")),
    ("🥇 T1 趋势", "GitHub本周新星", src_github),
    ("🥈 T2 验证", "CSDN热榜", src_csdn),
    ("🥈 T2 验证", "dev.to", src_devto),
    ("🥈 T2 验证", "贴吧", src_tieba),
    ("🥉 T3 发现", "今日头条", src_toutiao),
    ("🥈 T2 验证", "知乎热榜", src_zhihu),
    ("🥉 T3 发现", "澎湃新闻", src_paper),
    ("🥉 T3 发现", "掘金热榜", src_juejin),
    ("🥉 T3 发现", "量子位RSS", lambda: src_rss("https://www.qbitai.com/feed")),
    ("🥉 T3 发现", "InfoQ中文", lambda: src_rss("https://www.infoq.cn/feed")),
    ("🥉 T3 发现", "Solidot", lambda: src_rss("https://www.solidot.org/index.rss")),
    ("🎒 备用", "ProductHunt", lambda: src_rss("https://www.producthunt.com/feed", atom=True)),
]

def main():
    as_json = "--json" in sys.argv
    results = {}
    failed = []
    for group, name, fn in SOURCES:
        try:
            items = fn()
        except Exception:
            items = None
        if items:
            results.setdefault(group, []).append((name, items))
        else:
            failed.append(name)

    if as_json:
        print(json.dumps({
            "date": date.today().isoformat(),
            "sources": {g: {n: items for n, items in lst} for g, lst in results.items()},
            "failed": failed,
        }, ensure_ascii=False, indent=2))
        return

    # 人类可读输出
    print(f"═══ 热点雷达 · {date.today().isoformat()} ═══\n")
    for group, sources in results.items():
        print(f"── {group} ──")
        for name, items in sources:
            print(f"\n【{name}】")
            for i, it in enumerate(items[:8], 1):
                hot = f" | 热度={it['hot']}" if it["hot"] != "" else ""
                extra = f" | {it['extra']}" if it["extra"] else ""
                print(f"  {i}. {it['title'][:45]}{hot}{extra}")
        print()
    if failed:
        print(f"⚠️ 失败源: {', '.join(failed)}")
    print(f"\n✅ {sum(len(lst) for lst in results.values())}个源成功 · ❌ {len(failed)}个失败")

if __name__ == "__main__":
    main()

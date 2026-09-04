from agent.config import get_config
import json
import time
import urllib.parse
import urllib.request

_tavily_client = None
_searxng_url: str | None | ValueError = False  # False = 未探测


def _get_tavily_client():
    global _tavily_client
    if _tavily_client is None:
        from tavily import TavilyClient
        api_key = get_config("TAVILY_API_KEY")
        if not api_key:
            raise ValueError("未配置 TAVILY_API_KEY，请在设置中填写")
        _tavily_client = TavilyClient(api_key=api_key)
    return _tavily_client


def _get_searxng_url():
    """返回本地 searXNG JSON 端点；未配置/不可用返回 None。"""
    global _searxng_url
    if isinstance(_searxng_url, ValueError):
        raise _searxng_url
    if _searxng_url is False:
        raw = get_config("SEARXNG_URL")
        _searxng_url = raw if raw else None
    return _searxng_url


def _searxng_search(keyword: str, max_results: int) -> list[dict]:
    """本地 searXNG，返回与 Tavily 同构的 title/content/url 列表。"""
    endpoint = _get_searxng_url().rstrip("/") + "/search"
    query = urllib.parse.urlencode({
        "q": keyword,
        "format": "json",
        "language": "zh-CN",
    })
    req = urllib.request.Request(endpoint + "?" + query, headers={
        "User-Agent": "Mozilla/5.0 (content-agent)",
    })
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
    results = []
    for item in data.get("results", [])[:max_results]:
        results.append({
            "title": item.get("title", ""),
            "content": item.get("content", ""),
            "url": item.get("url", ""),
        })
    return results


def search(keyword: str, max_results: int = 5) -> list[dict]:
    """
    搜索关键词，返回结构化结果列表。
    每条结果包含 title、content、url 字段。
    优先 Tavily；未配置 Tavily key 时降级到本地 searXNG。
    """
    use_tavily = bool(get_config("TAVILY_API_KEY"))

    # Tavily requests can be reset by local/proxy network paths. Retry briefly,
    # then degrade to an empty result so the LLM can continue without live search.
    if use_tavily:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = _get_tavily_client().search(keyword, max_results=max_results)
                return response.get("results", [])
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
        print(f"  [Search] Tavily 暂时不可用，已跳过：{keyword} ({last_error})")
        return []

    try:
        return _searxng_search(keyword, max_results)
    except ValueError as exc:
        print(f"  [Search] {exc}")
        return []
    except Exception as exc:
        print(f"  [Search] searXNG 不可用，已跳过：{keyword} ({exc})")
        return []

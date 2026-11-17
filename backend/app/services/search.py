"""Controlled public web search & fetch for scenario strategies.

Privacy: only sanitized public target info is sent upstream; resume text,
names, phone numbers and secrets never enter search queries.
Safety: user-supplied URLs are validated against SSRF before fetching.
"""

import asyncio
import ipaddress
import re
import socket
from urllib.parse import urlparse

import httpx

from app.config import Settings
from app.services.llm import CloudModelError

USER_AGENT = "CareerPilot/0.1 (+public scenario research)"
MAX_PAGE_CHARS = 6000
MAX_RESULTS = 5


class SearchService:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.tavily_api_key)

    async def search(self, query: str, max_results: int = MAX_RESULTS) -> list[dict]:
        """Search public web via configured provider. Raises search_unavailable when no key."""
        if not self.configured:
            raise CloudModelError(503, "search_unavailable", "尚未配置联网检索服务，当前结果为未联网核验的通用建议。")
        query = query.strip()[:300]
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.settings.tavily_api_key,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": "basic",
                        "include_answer": False,
                    },
                )
        except httpx.TimeoutException:
            raise CloudModelError(504, "search_timeout", "公开信息检索超时，请稍后重试。") from None
        except httpx.RequestError:
            raise CloudModelError(503, "search_connection", "无法连接检索服务，请检查服务器外网。") from None
        if response.status_code in {401, 403}:
            raise CloudModelError(503, "search_auth", "检索服务鉴权失败，请检查服务端搜索配置。")
        if response.status_code == 429:
            raise CloudModelError(429, "search_rate_limit", "检索服务达到频率限制，请稍后重试。")
        if response.status_code != 200:
            raise CloudModelError(503, "search_failed", "检索服务暂时不可用。")
        try:
            data = response.json()
            results = data.get("results") or []
            return [
                {
                    "title": str(item.get("title", ""))[:200],
                    "url": str(item.get("url", ""))[:500],
                    "excerpt": str(item.get("content", ""))[:600],
                    "published_at": item.get("published_date"),
                }
                for item in results[:max_results]
                if item.get("url")
            ]
        except (ValueError, AttributeError, TypeError):
            raise CloudModelError(502, "search_invalid", "检索服务返回格式异常。") from None

    async def fetch_page(self, url: str) -> dict:
        """Fetch a public URL with SSRF protection. Returns extracted readable text."""
        await _assert_public_url(url)
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=False, headers={"User-Agent": USER_AGENT}) as client:
                current = url
                for _ in range(3):
                    response = await client.get(current)
                    if response.is_redirect:
                        target = response.headers.get("location", "")
                        if not target:
                            break
                        from urllib.parse import urljoin
                        current = urljoin(current, target)
                        await _assert_public_url(current)
                        continue
                    break
                else:
                    raise CloudModelError(422, "fetch_redirect_loop", "目标页面重定向过多，已停止读取。")
        except CloudModelError:
            raise
        except httpx.TimeoutException:
            raise CloudModelError(504, "fetch_timeout", "读取目标页面超时。") from None
        except httpx.RequestError:
            raise CloudModelError(503, "fetch_failed", "无法读取目标页面。") from None
        if response.status_code != 200:
            raise CloudModelError(422, "fetch_rejected", f"目标页面返回 {response.status_code}，无法读取。")
        content_type = response.headers.get("content-type", "")
        if "text" not in content_type and "html" not in content_type and "json" not in content_type:
            raise CloudModelError(422, "fetch_unsupported", "只读取公开网页文本，不下载文件。")
        text = _html_to_text(response.text)
        return {"url": str(response.url), "final_url": current, "content": text[:MAX_PAGE_CHARS], "content_status": "full_text" if len(text) > 400 else "snippet_only"}


async def _assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise CloudModelError(422, "url_scheme_blocked", "仅支持 http/https 公开链接。")
    host = parsed.hostname or ""
    if not host:
        raise CloudModelError(422, "url_invalid", "链接格式无效。")
    try:
        addresses = await asyncio.get_running_loop().run_in_executor(None, socket.getaddrinfo, host, None)
    except socket.gaierror:
        raise CloudModelError(422, "url_dns_failed", "链接域名无法解析。") from None
    for family, *_rest, sockaddr in addresses:
        ip = ipaddress.ip_address(sockaddr[0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise CloudModelError(422, "url_private_blocked", "目标地址指向内部网络，已阻止访问。")


def _html_to_text(raw: str) -> str:
    text = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw)
    text = re.sub(r"(?is)<!--.*?-->", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    for entity, char in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        text = text.replace(entity, char)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)

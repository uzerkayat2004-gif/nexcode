"""
NexCode Web Page Fetcher
~~~~~~~~~~~~~~~~~~~~~~~~~~

Fetches web pages and extracts clean text, markdown,
code blocks, and links.  Handles edge cases gracefully.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FetchedPage:
    """A fetched and parsed web page."""

    url: str = ""
    title: str = ""
    content: str = ""
    markdown: str = ""
    links: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    code_blocks: list[str] = field(default_factory=list)
    word_count: int = 0
    fetch_time_ms: int = 0
    status_code: int = 0


# ---------------------------------------------------------------------------
# WebFetcher
# ---------------------------------------------------------------------------

class WebFetcher:
    """
    Fetches and parses web pages into clean AI-ready text.

    Uses trafilatura for content extraction with httpx for
    async HTTP requests.  Handles timeouts, redirects, and
    binary content gracefully.
    """

    def __init__(self, timeout: int = 15, max_length: int = 50000) -> None:
        self.timeout = timeout
        self.max_length = max_length

    # ── Single fetch ───────────────────────────────────────────────────────

    async def fetch(
        self,
        url: str,
        extract_code: bool = True,
        max_length: int | None = None,
    ) -> FetchedPage:
        """Fetch a URL and return clean content."""
        max_len = max_length or self.max_length
        start = time.perf_counter()

        try:
            import httpx
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": "NexCode/1.0 (AI Coding Assistant)"},
            ) as client:
                resp = await client.get(url)
                status = resp.status_code
                html = resp.text
        except Exception as exc:
            elapsed = int((time.perf_counter() - start) * 1000)
            return FetchedPage(url=url, content=f"Fetch error: {exc}", fetch_time_ms=elapsed, status_code=0)

        # Extract content.
        content = ""
        title = ""
        try:
            import trafilatura
            content = trafilatura.extract(html, include_links=True, include_tables=True) or ""
            metadata = trafilatura.extract_metadata(html)
            if metadata:
                title = getattr(metadata, "title", "") or ""
        except ImportError:
            # Fallback: basic HTML stripping.
            content = _strip_html(html)
            title = _extract_title(html)

        # Extract code blocks from raw HTML.
        code_blocks: list[str] = []
        if extract_code:
            code_blocks = _extract_code_blocks(html)

        # Extract links.
        links = _extract_links(html, url)

        # Trim content.
        if len(content) > max_len:
            content = _smart_trim(content, max_len)

        elapsed = int((time.perf_counter() - start) * 1000)
        return FetchedPage(
            url=url,
            title=title,
            content=content,
            markdown=content,
            links=links[:50],
            images=_extract_images(html, url)[:20],
            code_blocks=code_blocks,
            word_count=len(content.split()),
            fetch_time_ms=elapsed,
            status_code=status,
        )

    # ── Parallel fetch ─────────────────────────────────────────────────────

    async def fetch_many(
        self,
        urls: list[str],
        max_parallel: int = 5,
    ) -> list[FetchedPage]:
        """Fetch multiple URLs in parallel."""
        semaphore = asyncio.Semaphore(max_parallel)

        async def _limited(u: str) -> FetchedPage:
            async with semaphore:
                return await self.fetch(u)

        return await asyncio.gather(*[_limited(u) for u in urls])

    # ── AI-powered summarize ───────────────────────────────────────────────

    async def fetch_and_summarize(
        self,
        url: str,
        question: str,
        ai_provider: Any,
    ) -> str:
        """Fetch a page and summarize it with AI focused on a question."""
        page = await self.fetch(url)
        if not page.content:
            return f"Could not fetch content from {url}"

        prompt = (
            f"Based on this web page content, answer this question: {question}\n\n"
            f"Page: {page.title}\nURL: {url}\n\n"
            f"Content:\n{page.content[:8000]}"
        )
        try:
            response = await ai_provider.chat(
                messages=[{"role": "user", "content": prompt}],
                system="You are a helpful research assistant. Be concise and factual.",
            )
            return getattr(response, "content", str(response))
        except Exception as exc:
            return f"Summary failed: {exc}"

    # ── Accessibility check ────────────────────────────────────────────────

    async def is_accessible(self, url: str) -> bool:
        """Check if URL is reachable."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5, follow_redirects=True) as client:
                resp = await client.head(url)
                return resp.status_code < 400
        except Exception:
            return False

    # ── Code extraction ────────────────────────────────────────────────────

    async def extract_code(self, url: str) -> list[str]:
        """Extract just code blocks from a page."""
        page = await self.fetch(url, extract_code=True)
        return page.code_blocks

    # ── Special site handlers ──────────────────────────────────────────────

    async def fetch_github(self, url: str) -> FetchedPage:
        """Fetch GitHub page — try raw content for files."""
        if "/blob/" in url:
            raw_url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
            return await self.fetch(raw_url)
        return await self.fetch(url)

    async def fetch_stackoverflow(self, url: str) -> FetchedPage:
        """Fetch Stack Overflow — extract answers."""
        return await self.fetch(url)

    async def fetch_npm(self, package: str) -> FetchedPage:
        """Fetch npm package info."""
        return await self.fetch(f"https://registry.npmjs.org/{package}")

    async def fetch_pypi(self, package: str) -> FetchedPage:
        """Fetch PyPI package info."""
        return await self.fetch(f"https://pypi.org/pypi/{package}/json")

    async def fetch_docs(self, url: str) -> FetchedPage:
        """Fetch documentation page."""
        return await self.fetch(url)


# ---------------------------------------------------------------------------
# HTML parsing helpers
# ---------------------------------------------------------------------------

def _strip_html(html: str) -> str:
    """Basic HTML stripping fallback."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()[:50000]


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def _extract_code_blocks(html: str) -> list[str]:
    """Extract code from <pre><code> and <code> blocks."""
    blocks: list[str] = []
    for match in re.finditer(r"<pre[^>]*>\s*<code[^>]*>(.*?)</code>\s*</pre>", html, re.DOTALL | re.IGNORECASE):
        code = re.sub(r"<[^>]+>", "", match.group(1))
        code = code.strip()
        if len(code) > 20:
            blocks.append(code)
    return blocks[:20]


def _extract_links(html: str, base_url: str) -> list[str]:
    """Extract href links."""
    links: list[str] = []
    for match in re.finditer(r'href=["\']([^"\']+)["\']', html):
        href = match.group(1)
        if href.startswith("http"):
            links.append(href)
        elif href.startswith("/"):
            parsed = urlparse(base_url)
            links.append(f"{parsed.scheme}://{parsed.netloc}{href}")
    return links


def _extract_images(html: str, base_url: str) -> list[str]:
    """Extract image src URLs."""
    images: list[str] = []
    for match in re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.IGNORECASE):
        src = match.group(1)
        if src.startswith("http"):
            images.append(src)
    return images


def _smart_trim(text: str, max_len: int) -> str:
    """Trim text without cutting mid-sentence."""
    if len(text) <= max_len:
        return text
    trimmed = text[:max_len]
    last_period = trimmed.rfind(".")
    if last_period > max_len * 0.8:
        return trimmed[:last_period + 1]
    return trimmed + "..."

"""
NexCode Web Search Engine
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Multi-provider web search with auto-selection.
Supports Tavily, Brave, SerpAPI, DuckDuckGo, and Exa.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """A single search result."""

    title: str = ""
    url: str = ""
    snippet: str = ""
    published_date: str | None = None
    source: str = ""
    relevance_score: float = 0.0


@dataclass
class SearchResponse:
    """Response from a search query."""

    query: str = ""
    results: list[SearchResult] = field(default_factory=list)
    total_results: int = 0
    search_time_ms: int = 0
    provider: str = ""


# ---------------------------------------------------------------------------
# Provider config
# ---------------------------------------------------------------------------

SEARCH_PROVIDERS: dict[str, dict[str, Any]] = {
    "tavily": {
        "env_key": "TAVILY_API_KEY",
        "free_tier": "1000 searches/month",
        "best_for": "general, research, news",
        "returns_full_content": True,
    },
    "brave": {
        "env_key": "BRAVE_SEARCH_API_KEY",
        "free_tier": "2000 searches/month",
        "best_for": "general, code, news",
        "returns_full_content": False,
    },
    "serpapi": {
        "env_key": "SERPAPI_KEY",
        "free_tier": "100 searches/month",
        "best_for": "most accurate Google results",
        "returns_full_content": False,
    },
    "duckduckgo": {
        "env_key": None,
        "free_tier": "unlimited",
        "best_for": "fallback, privacy",
        "returns_full_content": False,
    },
    "exa": {
        "env_key": "EXA_API_KEY",
        "free_tier": "1000 searches/month",
        "best_for": "semantic search, finding similar code",
        "returns_full_content": True,
    },
}


# ---------------------------------------------------------------------------
# WebSearchEngine
# ---------------------------------------------------------------------------

class WebSearchEngine:
    """
    Multi-provider web search with auto-selection.

    Priority: Tavily → Brave → Exa → SerpAPI → DuckDuckGo (always available).
    """

    def __init__(self) -> None:
        self._active_provider: str | None = None

    # ── Main search ────────────────────────────────────────────────────────

    async def search(
        self,
        query: str,
        max_results: int = 10,
        search_type: str = "general",
        date_filter: str | None = None,
    ) -> SearchResponse:
        """Search using the best available provider."""
        provider = self.get_active_provider()
        return await self.search_with(provider, query, max_results)

    async def search_with(
        self,
        provider: str,
        query: str,
        max_results: int = 10,
    ) -> SearchResponse:
        """Search with a specific provider."""
        start = time.perf_counter()
        results: list[SearchResult] = []

        try:
            if provider == "tavily":
                results = await self._search_tavily(query, max_results)
            elif provider == "brave":
                results = await self._search_brave(query, max_results)
            elif provider == "serpapi":
                results = await self._search_serpapi(query, max_results)
            elif provider == "exa":
                results = await self._search_exa(query, max_results)
            else:
                results = await self._search_duckduckgo(query, max_results)
        except Exception:
            # Fallback to DuckDuckGo.
            if provider != "duckduckgo":
                results = await self._search_duckduckgo(query, max_results)
                provider = "duckduckgo"

        elapsed = int((time.perf_counter() - start) * 1000)
        return SearchResponse(
            query=query,
            results=results,
            total_results=len(results),
            search_time_ms=elapsed,
            provider=provider,
        )

    # ── Provider detection ─────────────────────────────────────────────────

    def get_providers(self) -> list[str]:
        """Get list of all configured providers."""
        available: list[str] = []
        for name, config in SEARCH_PROVIDERS.items():
            env_key = config.get("env_key")
            if env_key is None or os.environ.get(env_key):
                available.append(name)
        return available

    def get_active_provider(self) -> str:
        """Get the best available provider."""
        if self._active_provider:
            return self._active_provider
        priority = ["tavily", "brave", "exa", "serpapi", "duckduckgo"]
        for p in priority:
            env_key = SEARCH_PROVIDERS[p].get("env_key")
            if env_key is None or os.environ.get(env_key):
                return p
        return "duckduckgo"

    # ── Provider implementations ───────────────────────────────────────────

    async def _search_tavily(self, query: str, max_results: int) -> list[SearchResult]:
        import httpx
        key = os.environ.get("TAVILY_API_KEY", "")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"query": query, "max_results": max_results, "api_key": key},
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=r.get("content", "")[:300],
                    source=_extract_domain(r.get("url", "")),
                    relevance_score=r.get("score", 0.0),
                )
                for r in data.get("results", [])
            ]

    async def _search_brave(self, query: str, max_results: int) -> list[SearchResult]:
        import httpx
        key = os.environ.get("BRAVE_SEARCH_API_KEY", "")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": max_results},
                headers={"X-Subscription-Token": key, "Accept": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=r.get("description", "")[:300],
                    source=_extract_domain(r.get("url", "")),
                )
                for r in data.get("web", {}).get("results", [])
            ]

    async def _search_serpapi(self, query: str, max_results: int) -> list[SearchResult]:
        import httpx
        key = os.environ.get("SERPAPI_KEY", "")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://serpapi.com/search",
                params={"q": query, "num": max_results, "api_key": key, "engine": "google"},
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("link", ""),
                    snippet=r.get("snippet", "")[:300],
                    source=_extract_domain(r.get("link", "")),
                )
                for r in data.get("organic_results", [])
            ]

    async def _search_exa(self, query: str, max_results: int) -> list[SearchResult]:
        import httpx
        key = os.environ.get("EXA_API_KEY", "")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.exa.ai/search",
                json={"query": query, "numResults": max_results, "useAutoprompt": True},
                headers={"x-api-key": key},
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=r.get("text", "")[:300],
                    source=_extract_domain(r.get("url", "")),
                    relevance_score=r.get("score", 0.0),
                )
                for r in data.get("results", [])
            ]

    async def _search_duckduckgo(self, query: str, max_results: int) -> list[SearchResult]:
        """DuckDuckGo — no API key needed, always available."""
        import asyncio

        def _do_search(q: str, n: int) -> list[dict]:
            from ddgs import DDGS
            with DDGS() as ddgs:
                return list(ddgs.text(q, max_results=n))

        def _parse(raw: list[dict]) -> list[SearchResult]:
            return [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("href", ""),
                    snippet=r.get("body", "")[:300],
                    source=_extract_domain(r.get("href", "")),
                )
                for r in raw
            ]

        try:
            # First attempt.
            raw = await asyncio.to_thread(_do_search, query, max_results)
            if raw:
                return _parse(raw)

            # Retry with simplified query after a short wait.
            await asyncio.sleep(2)
            simplified = " ".join(query.split()[:6])  # Keep first 6 words.
            raw = await asyncio.to_thread(_do_search, simplified, max_results)
            if raw:
                return _parse(raw)

            return [
                SearchResult(
                    title="No results found",
                    url="",
                    snippet=f"DuckDuckGo returned no results for: {query}",
                )
            ]
        except ImportError:
            return [
                SearchResult(
                    title="ddgs not installed",
                    url="",
                    snippet="Run: uv pip install ddgs",
                )
            ]
        except Exception as exc:
            return [
                SearchResult(
                    title="DuckDuckGo search failed",
                    url="",
                    snippet=f"Error: {exc}",
                )
            ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "")
    except Exception:
        return url[:30]

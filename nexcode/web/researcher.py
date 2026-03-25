"""
NexCode Deep Researcher
~~~~~~~~~~~~~~~~~~~~~~~~~

Orchestrates multi-query searches, parallel page fetching,
and AI synthesis into structured research reports.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console

from nexcode.web.fetcher import WebFetcher
from nexcode.web.search import SearchResult, WebSearchEngine

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ResearchSource:
    """A source used in the research report."""

    url: str = ""
    title: str = ""
    relevance: float = 0.0
    key_points: list[str] = field(default_factory=list)
    quote: str | None = None


@dataclass
class ResearchReport:
    """A complete research report."""

    query: str = ""
    summary: str = ""
    key_findings: list[str] = field(default_factory=list)
    sources: list[ResearchSource] = field(default_factory=list)
    code_examples: list[str] = field(default_factory=list)
    related_topics: list[str] = field(default_factory=list)
    confidence: float = 0.0
    research_time_ms: int = 0


# ---------------------------------------------------------------------------
# DeepResearcher
# ---------------------------------------------------------------------------


class DeepResearcher:
    """
    Deep research orchestrator.

    Flow: AI query expansion → parallel search → dedup →
    fetch top pages → AI synthesis → ResearchReport.
    """

    def __init__(
        self,
        search_engine: WebSearchEngine | None = None,
        fetcher: WebFetcher | None = None,
        ai_provider: Any = None,
        console: Console | None = None,
    ) -> None:
        self.search = search_engine or WebSearchEngine()
        self.fetcher = fetcher or WebFetcher()
        self.ai_provider = ai_provider
        self.console = console or Console()

    # ── Full deep research ─────────────────────────────────────────────────

    async def research(
        self,
        query: str,
        depth: str = "normal",
        focus: str = "general",
    ) -> ResearchReport:
        """Full deep research on a topic."""
        start = time.perf_counter()

        # Step 1: Generate search queries.
        queries = await self._expand_queries(query, depth)
        self._log(f"✅ Generated {len(queries)} search queries")

        # Step 2: Run all queries in parallel.
        all_results: list[SearchResult] = []
        search_tasks = [self.search.search(q, max_results=10, search_type=focus) for q in queries]
        responses = await asyncio.gather(*search_tasks, return_exceptions=True)

        for resp in responses:
            if hasattr(resp, "results"):
                all_results.extend(resp.results)

        # Dedup by URL.
        seen: set[str] = set()
        unique: list[SearchResult] = []
        for r in all_results:
            if r.url not in seen:
                seen.add(r.url)
                unique.append(r)

        self._log(f"✅ Found {len(unique)} results across all queries")

        # Step 3: Rank and fetch top pages.
        top_n = {"quick": 2, "normal": 5, "deep": 8}.get(depth, 5)
        top_results = unique[:top_n]

        urls = [r.url for r in top_results]
        pages = await self.fetcher.fetch_many(urls, max_parallel=5)

        fetched_count = 0
        for p in pages:
            if p.content:
                fetched_count += 1
        self._log(f"✅ Fetched {fetched_count} pages")

        # Step 4: Extract code blocks.
        code_examples: list[str] = []
        for page in pages:
            code_examples.extend(page.code_blocks[:3])

        # Step 5: AI synthesis.
        self._log("🔄 Synthesizing findings...")
        report = await self._synthesize(query, top_results, pages, code_examples)

        elapsed = int((time.perf_counter() - start) * 1000)
        report.research_time_ms = elapsed
        report.code_examples = code_examples[:5]

        self._log(f"✅ Research complete ({elapsed}ms)")
        return report

    # ── Quick answer ───────────────────────────────────────────────────────

    async def quick_answer(self, query: str) -> str:
        """Single search, summarize top results."""
        response = await self.search.search(query, max_results=5)
        if not response.results:
            return "No results found."

        snippets = "\n".join(f"- {r.title}: {r.snippet}" for r in response.results[:5])

        if self.ai_provider:
            try:
                prompt = f"Based on these search results, answer: {query}\n\n{snippets}"
                resp = await self.ai_provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    system="Be concise and factual. Cite sources.",
                )
                return getattr(resp, "content", str(resp))
            except Exception:
                pass

        return snippets

    # ── Code examples ──────────────────────────────────────────────────────

    async def find_code_examples(self, task: str, language: str) -> list[str]:
        """Find code examples for a task in a specific language."""
        query = f"{task} {language} code example"
        response = await self.search.search(query, max_results=5, search_type="code")

        urls = [r.url for r in response.results[:3]]
        pages = await self.fetcher.fetch_many(urls)

        examples: list[str] = []
        for page in pages:
            examples.extend(page.code_blocks[:3])
        return examples[:10]

    # ── Documentation ──────────────────────────────────────────────────────

    async def find_docs(self, library: str, topic: str | None = None) -> ResearchReport:
        """Find documentation for a library."""
        query = f"{library} documentation"
        if topic:
            query += f" {topic}"
        return await self.research(query, depth="normal", focus="docs")

    # ── Package version ────────────────────────────────────────────────────

    async def get_latest_version(self, package: str, ecosystem: str) -> str | None:
        """Get latest version of a package."""
        urls = {
            "npm": f"https://registry.npmjs.org/{package}/latest",
            "pypi": f"https://pypi.org/pypi/{package}/json",
        }
        url = urls.get(ecosystem)
        if not url:
            return None
        try:
            page = await self.fetcher.fetch(url)
            if "version" in page.content:
                import re

                match = re.search(r'"version"\s*:\s*"([^"]+)"', page.content)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return None

    # ── Internal ───────────────────────────────────────────────────────────

    async def _expand_queries(self, query: str, depth: str) -> list[str]:
        """Generate multiple search queries from the original."""
        queries = [query]

        if depth == "quick":
            return queries

        if self.ai_provider:
            try:
                n = 4 if depth == "deep" else 2
                prompt = (
                    f"Generate {n} different search queries to research this topic: {query}\n"
                    "Return only the queries, one per line."
                )
                resp = await self.ai_provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    system="You generate search queries. Return only queries, one per line.",
                )
                text = getattr(resp, "content", str(resp))
                extra = [
                    q.strip().strip("-").strip("0123456789.").strip()
                    for q in text.strip().splitlines()
                    if q.strip()
                ]
                queries.extend(extra[:n])
            except Exception:
                pass

        # Fallback expansions.
        if len(queries) < 3:
            queries.append(f"{query} tutorial example")
            queries.append(f"{query} best practices")

        return queries

    async def _synthesize(
        self,
        query: str,
        results: list[SearchResult],
        pages: list[Any],
        code_examples: list[str],
    ) -> ResearchReport:
        """AI synthesis of research findings."""
        sources = [
            ResearchSource(url=r.url, title=r.title, relevance=r.relevance_score) for r in results
        ]

        content_summary = "\n\n".join(
            f"Source: {p.title} ({p.url})\n{p.content[:2000]}" for p in pages if p.content
        )

        if self.ai_provider:
            try:
                prompt = (
                    f"Research query: {query}\n\n"
                    f"Sources:\n{content_summary[:8000]}\n\n"
                    "Provide:\n1. A 2-3 sentence summary\n"
                    "2. 3-5 key findings as bullet points\n"
                    "3. 2-3 related topics to explore"
                )
                resp = await self.ai_provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    system="You are a research analyst. Be factual and concise.",
                )
                text = getattr(resp, "content", str(resp))
                return ResearchReport(
                    query=query,
                    summary=text[:500],
                    key_findings=[
                        line.strip() for line in text.splitlines() if line.strip().startswith("-")
                    ][:5],
                    sources=sources,
                    confidence=0.8 if len(pages) >= 3 else 0.5,
                )
            except Exception:
                pass

        return ResearchReport(
            query=query,
            summary=f"Found {len(results)} results for '{query}'",
            sources=sources,
            confidence=0.3,
        )

    def _log(self, msg: str) -> None:
        self.console.print(f"  {msg}")

"""
NexCode Web Tools
~~~~~~~~~~~~~~~~~~~

7 web tools for AI to use: search, fetch, research,
code examples, package info, docs, and URL check.
"""

from __future__ import annotations

from typing import Any

from nexcode.tools.base import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web for documentation, examples, solutions, or any information"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "max_results": {"type": "integer", "description": "Max results (default 10)", "default": 10},
            "search_type": {"type": "string", "enum": ["general", "code", "news", "docs"], "default": "general"},
        },
        "required": ["query"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        from nexcode.web.search import WebSearchEngine
        engine = WebSearchEngine()
        query = kwargs["query"]
        max_results = kwargs.get("max_results", 10)
        search_type = kwargs.get("search_type", "general")

        response = await engine.search(query, max_results=max_results, search_type=search_type)

        if not response.results:
            return ToolResult(success=True, output="No results found.", display=f"🔍 No results for: {query}")

        output_lines = [f"Search: {query} ({response.provider}, {response.search_time_ms}ms)\n"]
        for i, r in enumerate(response.results, 1):
            output_lines.append(f"{i}. {r.title}\n   {r.url}\n   {r.snippet}\n")

        output = "\n".join(output_lines)
        display = f"🔍 {len(response.results)} results for '{query}' ({response.provider})"
        return ToolResult(success=True, output=output, display=display)


class FetchPageTool(BaseTool):
    name = "fetch_page"
    description = "Fetch a web page and return its clean text content"
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to fetch"},
            "extract_code": {"type": "boolean", "description": "Extract code blocks", "default": True},
        },
        "required": ["url"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        from nexcode.web.fetcher import WebFetcher
        fetcher = WebFetcher()
        url = kwargs["url"]
        extract_code = kwargs.get("extract_code", True)

        page = await fetcher.fetch(url, extract_code=extract_code)

        if page.status_code == 0:
            return ToolResult(success=False, output=page.content, display=f"❌ Failed to fetch {url}", error=page.content)

        output = f"Title: {page.title}\nURL: {url}\nWords: {page.word_count}\n\n{page.content[:10000]}"
        if page.code_blocks:
            output += "\n\n--- Code Blocks ---\n"
            for i, code in enumerate(page.code_blocks[:5], 1):
                output += f"\n[Block {i}]\n{code[:1000]}\n"

        display = f"🌐 Fetched: {page.title} ({page.word_count} words, {page.fetch_time_ms}ms)"
        return ToolResult(success=True, output=output, display=display)


class DeepResearchTool(BaseTool):
    name = "deep_research"
    description = "Run deep research on a topic — multiple searches, page fetches, and AI synthesis"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Research topic or question"},
            "depth": {"type": "string", "enum": ["quick", "normal", "deep"], "default": "normal"},
            "focus": {"type": "string", "enum": ["general", "code", "docs", "news"], "default": "general"},
        },
        "required": ["query"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        from nexcode.web.researcher import DeepResearcher
        researcher = DeepResearcher()
        query = kwargs["query"]

        report = await researcher.research(
            query, depth=kwargs.get("depth", "normal"), focus=kwargs.get("focus", "general"),
        )

        output = f"Research: {query}\n\nSummary:\n{report.summary}\n"
        if report.key_findings:
            output += "\nKey Findings:\n" + "\n".join(f"- {f}" for f in report.key_findings)
        if report.sources:
            output += "\n\nSources:\n" + "\n".join(f"- {s.title}: {s.url}" for s in report.sources[:5])
        if report.code_examples:
            output += "\n\nCode Examples:\n" + "\n".join(report.code_examples[:3])

        display = f"🔬 Research complete ({report.research_time_ms}ms, {len(report.sources)} sources)"
        return ToolResult(success=True, output=output, display=display)


class FindCodeExamplesTool(BaseTool):
    name = "find_code_examples"
    description = "Search the web for code examples for a specific task and language"
    parameters = {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "What the code should do"},
            "language": {"type": "string", "description": "Programming language"},
            "max_examples": {"type": "integer", "default": 5},
        },
        "required": ["task", "language"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        from nexcode.web.researcher import DeepResearcher
        researcher = DeepResearcher()
        examples = await researcher.find_code_examples(kwargs["task"], kwargs["language"])

        if not examples:
            return ToolResult(success=True, output="No code examples found.", display="No examples found")

        output = f"Code Examples for: {kwargs['task']} ({kwargs['language']})\n\n"
        for i, code in enumerate(examples[:kwargs.get("max_examples", 5)], 1):
            output += f"--- Example {i} ---\n{code[:800]}\n\n"

        display = f"💻 Found {len(examples)} code examples"
        return ToolResult(success=True, output=output, display=display)


class GetPackageInfoTool(BaseTool):
    name = "get_package_info"
    description = "Get info about an npm/PyPI/cargo package"
    parameters = {
        "type": "object",
        "properties": {
            "package": {
                "type": ["string", "array"],
                "items": {"type": "string"},
                "description": "Package name or list of packages"
            },
            "ecosystem": {"type": "string", "enum": ["npm", "pypi", "cargo", "go"]},
        },
        "required": ["package", "ecosystem"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        from nexcode.web.researcher import DeepResearcher
        researcher = DeepResearcher()
        package = kwargs["package"]
        eco = kwargs["ecosystem"]

        if eco in ("npm", "pypi"):
            result = await researcher.get_latest_version(package, eco)
            output = str(result)
        else:
            from nexcode.web.fetcher import WebFetcher
            fetcher = WebFetcher()
            if isinstance(package, list):
                # Just fetch the first one for crates since it's not fully supported in get_latest_version
                pkg = package[0] if package else ""
            else:
                pkg = package
            page = await fetcher.fetch(f"https://crates.io/api/v1/crates/{pkg}")
            output = page.content[:3000] if page.content else f"No info found for {pkg}"

        display = f"📦 {package} ({eco})"
        return ToolResult(success=True, output=output, display=display)


class FetchDocsTool(BaseTool):
    name = "fetch_docs"
    description = "Fetch official documentation for a library or framework"
    parameters = {
        "type": "object",
        "properties": {
            "library": {"type": "string", "description": "Library or framework name"},
            "topic": {"type": "string", "description": "Specific topic within the docs"},
        },
        "required": ["library"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        from nexcode.web.researcher import DeepResearcher
        researcher = DeepResearcher()
        report = await researcher.find_docs(kwargs["library"], kwargs.get("topic"))

        output = f"Docs: {kwargs['library']}\n\n{report.summary}\n"
        if report.sources:
            output += "\nSources:\n" + "\n".join(f"- {s.title}: {s.url}" for s in report.sources[:5])

        display = f"📖 Docs for {kwargs['library']}"
        return ToolResult(success=True, output=output, display=display)


class CheckUrlTool(BaseTool):
    name = "check_url"
    description = "Check if a URL is accessible and returns its HTTP status"
    parameters = {
        "type": "object",
        "properties": {"url": {"type": "string", "description": "URL to check"}},
        "required": ["url"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        from nexcode.web.fetcher import WebFetcher
        fetcher = WebFetcher()
        url = kwargs["url"]
        accessible = await fetcher.is_accessible(url)
        status = "✅ accessible" if accessible else "❌ not accessible"
        return ToolResult(success=True, output=f"{url}: {status}", display=f"🔗 {url}: {status}")


# ---------------------------------------------------------------------------
# All web tools for registry
# ---------------------------------------------------------------------------

ALL_WEB_TOOLS: list[type[BaseTool]] = [
    WebSearchTool,
    FetchPageTool,
    DeepResearchTool,
    FindCodeExamplesTool,
    GetPackageInfoTool,
    FetchDocsTool,
    CheckUrlTool,
]

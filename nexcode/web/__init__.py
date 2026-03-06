"""Web search and research system for NexCode."""

from nexcode.web.fetcher import FetchedPage, WebFetcher
from nexcode.web.researcher import DeepResearcher, ResearchReport, ResearchSource
from nexcode.web.search import SEARCH_PROVIDERS, SearchResponse, SearchResult, WebSearchEngine

__all__ = [
    "DeepResearcher",
    "FetchedPage",
    "ResearchReport",
    "ResearchSource",
    "SEARCH_PROVIDERS",
    "SearchResponse",
    "SearchResult",
    "WebFetcher",
    "WebSearchEngine",
]

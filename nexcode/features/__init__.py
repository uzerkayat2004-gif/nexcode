"""NexCode exclusive features package."""

from nexcode.features.analytics import ProjectAnalytics, ProjectStats, UsageStats
from nexcode.features.changelog import ChangelogGenerator
from nexcode.features.code_review import CodeReviewer, ReviewReport, CodeIssue, REVIEW_CATEGORIES
from nexcode.features.compare import ModelComparator, ComparisonResult, ModelResponse
from nexcode.features.documenter import AutoDocumenter, DocumentationResult, DocstringResult
from nexcode.features.explain import CodeExplainer, Explanation
from nexcode.features.optimizer import CostOptimizer, OptimizationSuggestion
from nexcode.features.pair import PairProgrammingSession, PairResult
from nexcode.features.profile import PerformanceProfiler, ProfileReport
from nexcode.features.security import SecurityScanner, SecurityReport, Vulnerability
from nexcode.features.templates import TemplateManager, BUILT_IN_TEMPLATES
from nexcode.features.workspace import WorkspaceManager, Project

__all__ = [
    "AutoDocumenter",
    "BUILT_IN_TEMPLATES",
    "ChangelogGenerator",
    "CodeExplainer",
    "CodeIssue",
    "CodeReviewer",
    "ComparisonResult",
    "CostOptimizer",
    "DocumentationResult",
    "DocstringResult",
    "Explanation",
    "ModelComparator",
    "ModelResponse",
    "OptimizationSuggestion",
    "PairProgrammingSession",
    "PairResult",
    "PerformanceProfiler",
    "ProfileReport",
    "Project",
    "ProjectAnalytics",
    "ProjectStats",
    "REVIEW_CATEGORIES",
    "ReviewReport",
    "SecurityReport",
    "SecurityScanner",
    "TemplateManager",
    "UsageStats",
    "Vulnerability",
    "WorkspaceManager",
]

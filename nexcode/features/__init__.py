"""NexCode exclusive features package."""

from nexcode.features.analytics import ProjectAnalytics, ProjectStats, UsageStats
from nexcode.features.changelog import ChangelogGenerator
from nexcode.features.code_review import REVIEW_CATEGORIES, CodeIssue, ReviewReport
from nexcode.features.compare import ComparisonResult, ModelComparator, ModelResponse
from nexcode.features.documenter import AutoDocumenter, DocstringResult, DocumentationResult
from nexcode.features.explain import CodeExplainer, Explanation
from nexcode.features.optimizer import CostOptimizer, OptimizationSuggestion
from nexcode.features.pair import PairProgrammingSession, PairResult
from nexcode.features.profile import PerformanceProfiler, ProfileReport
from nexcode.features.security import SecurityReport, SecurityScanner, Vulnerability
from nexcode.features.templates import BUILT_IN_TEMPLATES, TemplateManager
from nexcode.features.workspace import Project, WorkspaceManager

__all__ = [
    "AutoDocumenter",
    "BUILT_IN_TEMPLATES",
    "ChangelogGenerator",
    "CodeExplainer",
    "CodeIssue",
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

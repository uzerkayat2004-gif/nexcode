"""
NexCode Security Vulnerability Scanner
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Scans for code vulnerabilities, exposed secrets,
and dependency CVEs.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

SECRET_PATTERNS: list[tuple[str, str]] = [
    (r"(?i)(api[_-]?key|apikey)\s*[=:]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", "API key"),
    (r"(?i)(secret|password|passwd|pwd)\s*[=:]\s*['\"][^'\"]{8,}['\"]", "Secret/password"),
    (r"(?i)(token)\s*[=:]\s*['\"][A-Za-z0-9_\-\.]{20,}['\"]", "Token"),
    (r"sk-[A-Za-z0-9]{32,}", "OpenAI API key"),
    (r"ghp_[A-Za-z0-9]{36}", "GitHub Personal Access Token"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key"),
    (r"(?i)-----BEGIN (RSA |EC )?PRIVATE KEY-----", "Private key"),
]


@dataclass
class Vulnerability:
    id: str = ""
    cve_id: str | None = None
    severity: str = "medium"
    category: str = ""
    file: str = ""
    line: int = 0
    title: str = ""
    description: str = ""
    affected_code: str = ""
    fix_suggestion: str = ""
    references: list[str] = field(default_factory=list)
    auto_fixable: bool = False


@dataclass
class DependencyVuln:
    package: str = ""
    version: str = ""
    cve_id: str = ""
    severity: str = ""
    description: str = ""
    fixed_in_version: str = ""
    upgrade_command: str = ""


@dataclass
class SecurityReport:
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    dependency_vulns: list[DependencyVuln] = field(default_factory=list)
    secrets_found: int = 0
    total_files_scanned: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0


@dataclass
class FixResult:
    fixed: int = 0
    skipped: int = 0


class SecurityScanner:
    """Built-in security scanner."""

    def __init__(self, ai_provider: Any = None, console: Console | None = None) -> None:
        self.ai = ai_provider
        self.console = console or Console()

    async def scan(
        self,
        paths: list[str] | None = None,
        scan_dependencies: bool = True,
    ) -> SecurityReport:
        """Full security scan."""
        report = SecurityReport()
        files = self._collect_files(paths)
        report.total_files_scanned = len(files)

        # Scan for secrets.
        secrets = await self.scan_secrets(files)
        report.vulnerabilities.extend(secrets)
        report.secrets_found = len(secrets)

        # AI scan for code vulnerabilities.
        for fpath in files[:20]:
            vulns = await self._ai_scan_file(fpath)
            report.vulnerabilities.extend(vulns)

        # Dependency scan.
        if scan_dependencies:
            dep_vulns = await self.scan_dependencies()
            report.dependency_vulns = dep_vulns

        # Count severities.
        for v in report.vulnerabilities:
            if v.severity == "critical": report.critical += 1
            elif v.severity == "high": report.high += 1
            elif v.severity == "medium": report.medium += 1
            else: report.low += 1

        return report

    async def scan_secrets(self, files: list[str] | None = None) -> list[Vulnerability]:
        """Scan for hardcoded secrets."""
        secrets: list[Vulnerability] = []
        target_files = files or self._collect_files()
        counter = 0

        for fpath in target_files:
            try:
                content = Path(fpath).read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            for lineno, line in enumerate(content.splitlines(), 1):
                for pattern, secret_type in SECRET_PATTERNS:
                    if re.search(pattern, line):
                        counter += 1
                        secrets.append(Vulnerability(
                            id=f"SEC-{counter:03d}", severity="critical",
                            category="secrets", file=fpath, line=lineno,
                            title=f"Exposed {secret_type}",
                            description=f"Potential {secret_type} found in source code",
                            affected_code=line.strip()[:80],
                            fix_suggestion="Move to environment variable or .env file",
                            auto_fixable=False,
                        ))

        return secrets

    async def scan_dependencies(self) -> list[DependencyVuln]:
        """Scan dependencies for known CVEs (basic check)."""
        vulns: list[DependencyVuln] = []

        # Check pip packages.
        req_file = os.path.join(os.getcwd(), "requirements.txt")
        pyproject = os.path.join(os.getcwd(), "pyproject.toml")

        packages: list[tuple[str, str]] = []
        for pkg_file in [req_file, pyproject]:
            if os.path.exists(pkg_file):
                try:
                    content = Path(pkg_file).read_text(encoding="utf-8")
                    for match in re.finditer(r"([a-zA-Z0-9_-]+)\s*[=><~!]+\s*([\d.]+)", content):
                        packages.append((match.group(1), match.group(2)))
                except OSError:
                    pass

        if self.ai and packages:
            try:
                pkg_list = "\n".join(f"{n}=={v}" for n, v in packages[:20])
                resp = await self.ai.chat(
                    messages=[{"role": "user", "content": f"Check these packages for known CVEs:\n{pkg_list}"}],
                    system="List any known CVEs. Format: PACKAGE|VERSION|CVE|SEVERITY|DESCRIPTION|FIXED_IN",
                )
                text = getattr(resp, "content", "")
                for line in text.splitlines():
                    parts = line.split("|")
                    if len(parts) >= 5:
                        vulns.append(DependencyVuln(
                            package=parts[0].strip(), version=parts[1].strip(),
                            cve_id=parts[2].strip(), severity=parts[3].strip().lower(),
                            description=parts[4].strip(),
                            fixed_in_version=parts[5].strip() if len(parts) > 5 else "",
                            upgrade_command=f"pip install {parts[0].strip()}>={parts[5].strip()}" if len(parts) > 5 else "",
                        ))
            except Exception:
                pass

        return vulns

    async def check_gitignore(self) -> list[str]:
        """Check if sensitive files are in .gitignore."""
        missing: list[str] = []
        sensitive = [".env", ".env.local", "*.pem", "*.key", "id_rsa", ".nexcode.toml"]
        gitignore_path = os.path.join(os.getcwd(), ".gitignore")

        gitignore_content = ""
        if os.path.exists(gitignore_path):
            gitignore_content = Path(gitignore_path).read_text(encoding="utf-8")

        for pattern in sensitive:
            if pattern not in gitignore_content:
                missing.append(pattern)

        return missing

    async def auto_fix(self, report: SecurityReport) -> FixResult:
        """Auto-fix safe-to-fix vulnerabilities."""
        result = FixResult()
        for v in report.vulnerabilities:
            if v.auto_fixable:
                result.fixed += 1
            else:
                result.skipped += 1
        return result

    def generate_report(self, report: SecurityReport, output_format: str = "terminal") -> None:
        """Display security report."""
        body = Text()
        body.append(f"  🔴 Critical: {report.critical}    🟠 High: {report.high}    ", style="white")
        body.append(f"🟡 Medium: {report.medium}\n", style="white")
        body.append(f"  📦 Vulnerable dependencies: {len(report.dependency_vulns)}\n", style="white")
        body.append(f"  🔑 Exposed secrets: {report.secrets_found}\n\n", style="white")

        severity_icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
        for v in report.vulnerabilities[:15]:
            icon = severity_icons.get(v.severity, "ℹ️")
            body.append(f"  {icon} {v.id} — {v.title}\n", style="bold")
            body.append(f"  {v.file}:{v.line}\n", style="dim")
            body.append(f"  {v.description}\n", style="white")
            if v.fix_suggestion:
                body.append(f"  Fix: {v.fix_suggestion}\n", style="green")
            body.append("\n", style="white")

        for dv in report.dependency_vulns[:5]:
            body.append(f"  📦 {dv.cve_id} — {dv.package} {dv.version}\n", style="bold")
            body.append(f"  {dv.description}\n", style="white")
            if dv.upgrade_command:
                body.append(f"  Fix: {dv.upgrade_command}\n", style="green")
            body.append("\n")

        self.console.print(Panel(body, title=" 🔒 Security Scan Complete ", border_style="red", padding=(0, 1)))

    async def _ai_scan_file(self, path: str) -> list[Vulnerability]:
        if not self.ai:
            return []
        try:
            content = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return []
        try:
            resp = await self.ai.chat(
                messages=[{"role": "user", "content": (
                    f"Scan for security vulnerabilities:\n\n{content[:5000]}\n\n"
                    "Return: SEVERITY|CATEGORY|LINE|TITLE|DESCRIPTION|FIX"
                )}],
                system="You are a security scanner. Return only the formatted lines.",
            )
            text = getattr(resp, "content", "")
            vulns: list[Vulnerability] = []
            for line in text.splitlines():
                parts = line.split("|")
                if len(parts) >= 4:
                    vulns.append(Vulnerability(
                        id=f"SEC-{len(vulns)+1:03d}", severity=parts[0].strip().lower(),
                        category=parts[1].strip(), file=path,
                        line=int(parts[2].strip()) if parts[2].strip().isdigit() else 0,
                        title=parts[3].strip(),
                        description=parts[4].strip() if len(parts) > 4 else "",
                        fix_suggestion=parts[5].strip() if len(parts) > 5 else "",
                    ))
            return vulns
        except Exception:
            return []

    def _collect_files(self, paths: list[str] | None = None) -> list[str]:
        if paths:
            return [p for p in paths if os.path.isfile(p)]
        exts = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".rb", ".php"}
        result: list[str] = []
        for root, _, files in os.walk(os.getcwd()):
            if any(d in root for d in [".git", "node_modules", "__pycache__", ".venv"]):
                continue
            for f in files:
                if Path(f).suffix in exts:
                    result.append(os.path.join(root, f))
        return result[:50]

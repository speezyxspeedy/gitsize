"""Detection and recommendation engine for common missing .gitignore rules."""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Sequence

from gitsize.formatting import format_bytes
from gitsize.repository import RepositoryInfo, run_git_command


@dataclass(frozen=True)
class IgnoreRecommendation:
    """A recommended .gitignore rule based on detected repository artifacts."""

    suggested_pattern: str
    category: str
    detected_path: str
    reason: str
    matched_files_count: int
    total_size_bytes: int

    @property
    def formatted_size(self) -> str:
        """Return human-readable size of unignored artifacts."""
        return format_bytes(self.total_size_bytes)


# Catalog of common development artifacts to audit
CANDIDATE_RULES = [
    {
        "suggested_pattern": ".venv/",
        "category": "Virtual Environments",
        "names": [".venv", "venv", "env", ".env_test"],
        "is_dir": True,
        "reason": (
            "Python virtual environments contain platform-specific binaries, pip wheels, "
            "and external libraries that bloat repositories and break across systems."
        ),
    },
    {
        "suggested_pattern": "__pycache__/",
        "category": "Python Bytecode",
        "names": ["__pycache__"],
        "is_dir": True,
        "reason": (
            "Compiled Python bytecode directories contain platform-dependent *.pyc files "
            "that regenerate automatically and lead to frequent Git merge conflicts."
        ),
    },
    {
        "suggested_pattern": "node_modules/",
        "category": "JavaScript Dependencies",
        "names": ["node_modules"],
        "is_dir": True,
        "reason": (
            "Node.js package installations can contain tens of thousands of nested files. "
            "Dependencies must be managed via package.json / lockfiles instead."
        ),
    },
    {
        "suggested_pattern": ".env",
        "category": "Environment & Secrets",
        "names": [".env", ".env.local", ".env.development", ".env.production", ".env.test"],
        "is_dir": False,
        "reason": (
            "Environment configuration files frequently contain sensitive API keys, database "
            "credentials, and private tokens that should never be tracked in version control."
        ),
    },
    {
        "suggested_pattern": "dist/",
        "category": "Build Artifacts",
        "names": ["dist", "build", "out", "target"],
        "is_dir": True,
        "reason": (
            "Compilation outputs, distribution bundles, and binaries should be generated "
            "by reproducible automated builds or CI/CD pipelines, not checked into Git."
        ),
    },
    {
        "suggested_pattern": ".pytest_cache/",
        "category": "Test Caches",
        "names": [".pytest_cache", ".mypy_cache", ".ruff_cache", ".coverage", "htmlcov"],
        "is_dir": True,
        "reason": (
            "Test runners, linters, and type checkers generate local cache directories "
            "that churn on every test execution."
        ),
    },
    {
        "suggested_pattern": ".DS_Store",
        "category": "Operating System",
        "names": [".DS_Store"],
        "is_dir": False,
        "reason": (
            "macOS Finder creates hidden .DS_Store files storing view attributes, "
            "window positions, and icon layouts that create noisy commits."
        ),
    },
    {
        "suggested_pattern": "Thumbs.db",
        "category": "Operating System",
        "names": ["Thumbs.db", "ehthumbs.db"],
        "is_dir": False,
        "reason": (
            "Windows Explorer creates hidden Thumbs.db files to cache image previews, "
            "polluting cross-platform repositories."
        ),
    },
    {
        "suggested_pattern": ".idea/",
        "category": "IDE / Editor State",
        "names": [".idea"],
        "is_dir": True,
        "reason": (
            "JetBrains IDE directories store local developer indexes, window layouts, "
            "and workspace history that belong in local development settings."
        ),
    },
    {
        "suggested_pattern": ".vscode/",
        "category": "IDE / Editor State",
        "names": [".vscode"],
        "is_dir": True,
        "reason": (
            "VS Code folders often include personal user settings and local launch configurations. "
            "Unless team tasks are strictly shared, editor state should be ignored."
        ),
    },
]


def is_path_git_ignored(repo_root: Path, relative_path: str) -> bool:
    """Check if Git currently ignores a given path using git check-ignore.

    Args:
        repo_root: Root path of the repository.
        relative_path: Path relative to repository root.

    Returns:
        True if git considers the path ignored, False otherwise.
    """
    proc = run_git_command(["check-ignore", "-q", "--", relative_path], cwd=repo_root)
    # git check-ignore exits with 0 if ignored, 1 if not ignored
    return proc.returncode == 0


def calculate_path_storage(path: Path) -> tuple[int, int]:
    """Calculate the count of files and total size of a path safely.

    Never reads file contents (secrets are completely safe).

    Args:
        path: Path to inspect.

    Returns:
        Tuple of (file_count, total_bytes).
    """
    if not path.exists():
        return 0, 0

    if path.is_file():
        try:
            return 1, path.stat(follow_symlinks=False).st_size
        except OSError:
            return 1, 0

    total_count = 0
    total_bytes = 0
    try:
        for root, _, files in os.walk(path):
            for f in files:
                f_path = Path(root) / f
                try:
                    stat = f_path.stat(follow_symlinks=False)
                    total_bytes += stat.st_size
                    total_count += 1
                except OSError:
                    total_count += 1
    except OSError:
        pass

    return total_count, total_bytes


def read_existing_gitignore_patterns(repo_root: Path) -> set[str]:
    """Read patterns defined in root .gitignore without modifying it.

    Args:
        repo_root: Repository root path.

    Returns:
        Set of normalized pattern strings.
    """
    gitignore_path = repo_root / ".gitignore"
    patterns: set[str] = set()

    if not gitignore_path.is_file():
        return patterns

    try:
        with open(gitignore_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    # Normalize pattern: remove leading/trailing slashes for comparison
                    patterns.add(stripped)
                    patterns.add(stripped.strip("/"))
    except OSError:
        pass

    return patterns


def check_gitignore_recommendations(
    repo_info: RepositoryInfo,
) -> list[IgnoreRecommendation]:
    """Inspect repository working tree for common unignored development artifacts.

    Read-only audit:
    - Never modifies .gitignore
    - Never prints or reads secret contents (e.g. .env files)
    - Avoids duplicate suggestions
    - Checks both git check-ignore and existing .gitignore patterns

    Args:
        repo_info: Repository metadata.

    Returns:
        List of actionable IgnoreRecommendation objects.
    """
    root = repo_info.root_path
    existing_patterns = read_existing_gitignore_patterns(root)
    recommendations: list[IgnoreRecommendation] = []
    seen_suggested_patterns: set[str] = set()

    for rule in CANDIDATE_RULES:
        suggested = rule["suggested_pattern"]
        if suggested in seen_suggested_patterns:
            continue

        category = rule["category"]
        reason = rule["reason"]
        names: list[str] = rule["names"]
        is_dir: bool = rule["is_dir"]

        # Search for candidates at repository root and immediate subdirectories
        detected_candidate: Path | None = None
        for name in names:
            candidate = root / name
            if candidate.exists():
                if is_dir and candidate.is_dir():
                    detected_candidate = candidate
                    break
                elif not is_dir and candidate.is_file():
                    detected_candidate = candidate
                    break

        # If not found at root, check if any exists in one level of subdirectories
        # (e.g. backend/__pycache__ or frontend/node_modules)
        if not detected_candidate:
            try:
                for entry in os.scandir(root):
                    if entry.is_dir(follow_symlinks=False) and entry.name != ".git":
                        for name in names:
                            nested = Path(entry.path) / name
                            if nested.exists():
                                if is_dir and nested.is_dir():
                                    detected_candidate = nested
                                    break
                                elif not is_dir and nested.is_file():
                                    detected_candidate = nested
                                    break
                        if detected_candidate:
                            break
            except OSError:
                pass

        if not detected_candidate:
            continue

        try:
            rel_path = str(detected_candidate.relative_to(root)).replace("\\", "/")
        except ValueError:
            rel_path = detected_candidate.name

        # Check if already ignored by Git
        if is_path_git_ignored(root, rel_path):
            continue

        # Check if pattern is already represented in .gitignore file
        clean_suggested = suggested.strip("/")
        if clean_suggested in existing_patterns or suggested in existing_patterns:
            continue

        # Calculate impact without reading content
        file_count, total_bytes = calculate_path_storage(detected_candidate)

        seen_suggested_patterns.add(suggested)
        recommendations.append(
            IgnoreRecommendation(
                suggested_pattern=suggested,
                category=category,
                detected_path=rel_path,
                reason=reason,
                matched_files_count=file_count,
                total_size_bytes=total_bytes,
            )
        )

    return recommendations

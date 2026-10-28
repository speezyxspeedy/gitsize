"""Read-only working-tree filesystem scanner and storage aggregator."""

from collections import defaultdict
from dataclasses import dataclass
import fnmatch
import os
from pathlib import Path
from typing import Sequence

from gitsize.formatting import format_bytes
from gitsize.repository import RepositoryInfo

DEFAULT_EXCLUDES = [
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
]


@dataclass(frozen=True)
class FileInfo:
    """Metadata for a scanned working tree file."""

    path: Path
    relative_path: str
    size_bytes: int
    extension: str

    @property
    def formatted_size(self) -> str:
        """Return human-readable file size."""
        return format_bytes(self.size_bytes)


@dataclass(frozen=True)
class FileTypeStat:
    """Aggregated statistics for a specific file type extension."""

    extension: str
    count: int
    total_size_bytes: int
    percentage: float

    @property
    def formatted_size(self) -> str:
        """Return human-readable total size for this type."""
        return format_bytes(self.total_size_bytes)


@dataclass(frozen=True)
class ScanWarning:
    """Non-fatal warning recorded during repository scanning."""

    path: str
    reason: str


@dataclass(frozen=True)
class WorkingTreeScanResult:
    """Complete summary of a working-tree scan."""

    repository_info: RepositoryInfo
    total_files: int
    total_size_bytes: int
    largest_files: list[FileInfo]
    file_type_stats: list[FileTypeStat]
    warnings: list[ScanWarning]
    excluded_patterns: list[str]
    git_dir_size_bytes: int

    @property
    def formatted_total_size(self) -> str:
        """Return human-readable total working tree size."""
        return format_bytes(self.total_size_bytes)

    @property
    def formatted_git_dir_size(self) -> str:
        """Return human-readable .git metadata size."""
        return format_bytes(self.git_dir_size_bytes)


def is_excluded(rel_path: Path, exclude_patterns: Sequence[str]) -> bool:
    """Determine whether a path matches any exclusion patterns.

    Checks each path component as well as full relative glob matches.
    """
    parts = rel_path.parts
    posix_str = rel_path.as_posix()

    for pattern in exclude_patterns:
        cleaned_pattern = pattern.strip().strip("/\\")
        if not cleaned_pattern:
            continue

        # Exact match against any folder in path hierarchy
        if cleaned_pattern in parts:
            return True

        # Glob match against full relative path
        if fnmatch.fnmatch(posix_str, cleaned_pattern) or fnmatch.fnmatch(
            rel_path.name, cleaned_pattern
        ):
            return True

        # Handle directory-style glob patterns like 'dir/*'
        if fnmatch.fnmatch(posix_str, f"{cleaned_pattern}/*") or fnmatch.fnmatch(
            posix_str, f"*/{cleaned_pattern}/*"
        ):
            return True

    return False


def get_file_extension(path: Path) -> str:
    """Extract a normalized file extension or category."""
    suffix = path.suffix.lower()
    if suffix:
        return suffix
    # Handle files with no dot or dotfiles without an extra extension (e.g., .gitignore, Dockerfile)
    name = path.name
    if name.startswith(".") and len(name) > 1:
        return name
    return "(no extension)"


def scan_working_tree(
    repo_info: RepositoryInfo,
    top_n: int = 10,
    user_excludes: Sequence[str] | None = None,
    use_default_excludes: bool = True,
) -> WorkingTreeScanResult:
    """Perform a read-only scan of the repository working tree.

    Discovers all tracked and untracked files, identifies the largest files,
    groups storage by extension, and records non-fatal warnings for skipped paths.

    Args:
        repo_info: Repository metadata detected for the target repository.
        top_n: Number of largest files to report (default: 10).
        user_excludes: Optional user-supplied directory or glob patterns to exclude.
        use_default_excludes: Whether to include standard defaults (e.g. node_modules, .venv).

    Returns:
        WorkingTreeScanResult containing size summaries, top files, and warnings.
    """
    root = repo_info.root_path

    # Build active exclusions (.git is ALWAYS excluded from working tree scans)
    active_excludes: list[str] = [".git"]
    if use_default_excludes:
        for exc in DEFAULT_EXCLUDES:
            if exc not in active_excludes:
                active_excludes.append(exc)
    if user_excludes:
        for exc in user_excludes:
            clean = exc.strip()
            if clean and clean not in active_excludes:
                active_excludes.append(clean)

    scanned_files: list[FileInfo] = []
    warnings: list[ScanWarning] = []
    type_counts: dict[str, int] = defaultdict(int)
    type_sizes: dict[str, int] = defaultdict(int)

    # Breadth-first directory traversal with symlink and permission guards
    dirs_to_visit = [root]
    visited_real_dirs: set[Path] = set()

    try:
        real_root = root.resolve()
        visited_real_dirs.add(real_root)
    except OSError:
        real_root = root

    while dirs_to_visit:
        current_dir = dirs_to_visit.pop(0)

        try:
            entries = list(os.scandir(current_dir))
        except PermissionError as err:
            try:
                rel = current_dir.relative_to(root)
            except ValueError:
                rel = current_dir
            warnings.append(ScanWarning(path=str(rel), reason=f"Permission denied: {err}"))
            continue
        except (FileNotFoundError, OSError) as err:
            try:
                rel = current_dir.relative_to(root)
            except ValueError:
                rel = current_dir
            warnings.append(ScanWarning(path=str(rel), reason=f"Could not scan directory: {err}"))
            continue

        for entry in entries:
            entry_path = Path(entry.path)
            try:
                rel_path = entry_path.relative_to(root)
            except ValueError:
                rel_path = entry_path

            # Check if this item matches exclusion rules
            if is_excluded(rel_path, active_excludes):
                continue

            # Handle symbolic links safely
            try:
                is_sym = entry.is_symlink()
            except OSError as err:
                warnings.append(
                    ScanWarning(path=str(rel_path), reason=f"Failed to inspect symlink: {err}")
                )
                continue

            if is_sym:
                try:
                    resolved_target = entry_path.resolve()
                    # Check whether the target resides inside the repository
                    resolved_target.relative_to(real_root)
                except ValueError:
                    # Target is outside repository boundary
                    warnings.append(
                        ScanWarning(
                            path=str(rel_path),
                            reason="Skipped symbolic link pointing outside repository boundary.",
                        )
                    )
                    continue
                except (PermissionError, FileNotFoundError, OSError) as err:
                    warnings.append(
                        ScanWarning(
                            path=str(rel_path),
                            reason=f"Failed to resolve symbolic link: {err}",
                        )
                    )
                    continue

                # If symlink points to a directory inside the repo, do not recurse into it
                # to prevent duplicate stats or cyclic loops
                if resolved_target.is_dir():
                    warnings.append(
                        ScanWarning(
                            path=str(rel_path),
                            reason="Skipped directory symlink to prevent cyclic traversal.",
                        )
                    )
                    continue

            # Process directory
            try:
                if entry.is_dir(follow_symlinks=False):
                    try:
                        real_dir = entry_path.resolve()
                        if real_dir in visited_real_dirs:
                            continue
                        visited_real_dirs.add(real_dir)
                    except OSError:
                        pass
                    dirs_to_visit.append(entry_path)
                    continue
            except OSError as err:
                warnings.append(
                    ScanWarning(path=str(rel_path), reason=f"Failed to inspect directory: {err}")
                )
                continue

            # Process file
            try:
                stat_result = entry.stat(follow_symlinks=False)
                file_size = stat_result.st_size
                ext = get_file_extension(entry_path)

                file_info = FileInfo(
                    path=entry_path,
                    relative_path=str(rel_path).replace("\\", "/"),
                    size_bytes=file_size,
                    extension=ext,
                )
                scanned_files.append(file_info)

                type_counts[ext] += 1
                type_sizes[ext] += file_size

            except FileNotFoundError:
                # File disappeared between directory scan and stat
                warnings.append(
                    ScanWarning(
                        path=str(rel_path),
                        reason="File disappeared or was removed during scan.",
                    )
                )
            except PermissionError as err:
                warnings.append(
                    ScanWarning(path=str(rel_path), reason=f"Permission denied reading file: {err}")
                )
            except OSError as err:
                warnings.append(
                    ScanWarning(path=str(rel_path), reason=f"Filesystem error reading file: {err}")
                )

    # Calculate totals
    total_files = len(scanned_files)
    total_size_bytes = sum(f.size_bytes for f in scanned_files)

    # Sort largest files descending
    scanned_files.sort(key=lambda item: item.size_bytes, reverse=True)
    largest_files = scanned_files[: max(1, top_n)] if top_n > 0 else scanned_files

    # Build file type stats sorted by total size descending
    file_type_stats: list[FileTypeStat] = []
    for ext, size in sorted(type_sizes.items(), key=lambda x: x[1], reverse=True):
        count = type_counts[ext]
        pct = (size / total_size_bytes * 100.0) if total_size_bytes > 0 else 0.0
        file_type_stats.append(
            FileTypeStat(
                extension=ext,
                count=count,
                total_size_bytes=size,
                percentage=round(pct, 2),
            )
        )

    return WorkingTreeScanResult(
        repository_info=repo_info,
        total_files=total_files,
        total_size_bytes=total_size_bytes,
        largest_files=largest_files,
        file_type_stats=file_type_stats,
        warnings=warnings,
        excluded_patterns=active_excludes,
        git_dir_size_bytes=repo_info.git_dir_size_bytes,
    )

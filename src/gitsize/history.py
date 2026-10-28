"""Git history analyzer for discovering large historical objects and deleted files."""

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Sequence

from gitsize.formatting import format_bytes
from gitsize.repository import RepositoryInfo, run_git_command


@dataclass(frozen=True)
class HistoricalBlob:
    """Metadata for a Git blob object discovered in historical commits."""

    blob_hash: str
    short_hash: str
    size_bytes: int
    path: str
    commit_ref: str | None
    is_deleted_in_working_tree: bool

    @property
    def formatted_size(self) -> str:
        """Return human-readable uncompressed Git blob size."""
        return format_bytes(self.size_bytes)


@dataclass(frozen=True)
class GitHistoryAnalysis:
    """Summary of Git object storage analysis."""

    is_empty: bool
    is_shallow: bool
    total_blobs_found: int
    total_blob_bytes: int
    top_blobs: list[HistoricalBlob]
    notes: list[str]

    @property
    def formatted_total_size(self) -> str:
        """Return human-readable total uncompressed blob size."""
        return format_bytes(self.total_blob_bytes)


def analyze_git_history(
    repo_info: RepositoryInfo,
    top_n: int = 10,
) -> GitHistoryAnalysis:
    """Analyze Git repository history to locate large historical file blobs.

    Deduplicates identical blobs by hash, identifies files deleted from the
    current working tree, and extracts commit references for the top results.

    Read-only guarantee: Never modifies history, references, or the working tree.

    Args:
        repo_info: Detected repository metadata.
        top_n: Maximum number of largest historical objects to report.

    Returns:
        GitHistoryAnalysis with deduplicated large blobs and contextual notes.
    """
    root = repo_info.root_path
    notes: list[str] = [
        "Historical sizes reflect uncompressed Git blob object sizes, not compressed packfile disk usage.",
        "Deleted files still remain in Git history and contribute to repository clone download sizes.",
    ]

    if repo_info.is_empty:
        return GitHistoryAnalysis(
            is_empty=True,
            is_shallow=repo_info.is_shallow,
            total_blobs_found=0,
            total_blob_bytes=0,
            top_blobs=[],
            notes=["Repository has no commits yet. History analysis is unavailable."],
        )

    if repo_info.is_shallow:
        notes.append(
            "Repository is a shallow clone; analysis only covers locally available commit history."
        )

    # Step 1: Discover all historical objects and paths using rev-list
    proc_rev = run_git_command(["rev-list", "--objects", "--all"], cwd=root, timeout=60.0)
    if proc_rev.returncode != 0:
        return GitHistoryAnalysis(
            is_empty=False,
            is_shallow=repo_info.is_shallow,
            total_blobs_found=0,
            total_blob_bytes=0,
            top_blobs=[],
            notes=[f"Git rev-list failed: {proc_rev.stderr.strip()}"],
        )

    # Map blob_hash -> historical_path (only entries with an associated path are file blobs)
    hash_to_path: dict[str, str] = {}
    for line in proc_rev.stdout.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2:
            obj_hash, path = parts
            if obj_hash not in hash_to_path:
                hash_to_path[obj_hash] = path

    if not hash_to_path:
        return GitHistoryAnalysis(
            is_empty=False,
            is_shallow=repo_info.is_shallow,
            total_blobs_found=0,
            total_blob_bytes=0,
            top_blobs=[],
            notes=notes,
        )

    # Step 2: Query sizes and types in bulk using git cat-file --batch-check
    input_hashes = "\n".join(hash_to_path.keys())
    try:
        proc_cat = subprocess.run(
            ["git", "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
            input=input_hashes,
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60.0,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as err:
        return GitHistoryAnalysis(
            is_empty=False,
            is_shallow=repo_info.is_shallow,
            total_blobs_found=0,
            total_blob_bytes=0,
            top_blobs=[],
            notes=[f"Git cat-file batch-check failed: {err}"],
        )

    # Step 3: Filter for blobs and deduplicate
    blob_entries: list[tuple[int, str, str]] = []  # (size, hash, path)
    total_blob_bytes = 0

    for line in proc_cat.stdout.splitlines():
        parts = line.strip().split()
        if len(parts) >= 3:
            obj_hash, obj_type, size_str = parts[0], parts[1], parts[2]
            if obj_type == "blob":
                try:
                    size = int(size_str)
                    path = hash_to_path.get(obj_hash, "(unknown path)")
                    blob_entries.append((size, obj_hash, path))
                    total_blob_bytes += size
                except ValueError:
                    continue

    # Sort descending by size
    blob_entries.sort(key=lambda item: item[0], reverse=True)
    total_blobs_found = len(blob_entries)

    # Take top N
    selected_blobs = blob_entries[: max(1, top_n)] if top_n > 0 else blob_entries

    # Step 4: Resolve commit references and working tree status only for top-N blobs
    top_blobs: list[HistoricalBlob] = []
    for size, blob_hash, path in selected_blobs:
        short_hash = blob_hash[:8]

        # Check whether file is currently deleted in the working tree
        current_file_path = root / Path(path)
        is_deleted = not current_file_path.exists()

        # Find introducing commit
        commit_ref: str | None = None
        proc_log = run_git_command(
            ["log", "-1", f"--find-object={blob_hash}", "--format=%h %s"],
            cwd=root,
            timeout=10.0,
        )
        if proc_log.returncode == 0 and proc_log.stdout.strip():
            commit_ref = proc_log.stdout.strip()
        else:
            # Fallback to path log
            proc_path_log = run_git_command(
                ["log", "-1", "--format=%h %s", "--", path],
                cwd=root,
                timeout=10.0,
            )
            if proc_path_log.returncode == 0 and proc_path_log.stdout.strip():
                commit_ref = proc_path_log.stdout.strip()

        top_blobs.append(
            HistoricalBlob(
                blob_hash=blob_hash,
                short_hash=short_hash,
                size_bytes=size,
                path=path,
                commit_ref=commit_ref,
                is_deleted_in_working_tree=is_deleted,
            )
        )

    return GitHistoryAnalysis(
        is_empty=False,
        is_shallow=repo_info.is_shallow,
        total_blobs_found=total_blobs_found,
        total_blob_bytes=total_blob_bytes,
        top_blobs=top_blobs,
        notes=notes,
    )

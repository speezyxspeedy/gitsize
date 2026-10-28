"""Repository detection, Git CLI execution, and metadata inspection."""

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Sequence

from gitsize.exceptions import (
    GitNotFoundError,
    GitSizeError,
    NotAGitRepositoryError,
)


@dataclass(frozen=True)
class RepositoryInfo:
    """Metadata describing a detected Git repository."""

    root_path: Path
    working_dir: Path
    current_branch: str | None
    is_empty: bool
    is_shallow: bool
    git_dir_size_bytes: int


def run_git_command(
    args: Sequence[str],
    cwd: Path | None = None,
    timeout: float = 30.0,
) -> subprocess.CompletedProcess[str]:
    """Execute a Git CLI command safely using argument arrays and timeouts.

    Args:
        args: Command-line arguments to pass to git (e.g. ['rev-parse', '--show-toplevel']).
        cwd: Working directory in which to execute the command.
        timeout: Maximum seconds to wait before raising a TimeoutExpired error.

    Returns:
        subprocess.CompletedProcess containing stdout, stderr, and exit code.

    Raises:
        GitNotFoundError: If git executable is missing from system PATH.
        GitSizeError: If the command times out or encounters unexpected system failures.
    """
    cmd = ["git", *args]
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as err:
        raise GitNotFoundError(
            "Git is not installed or not available in the system PATH. "
            "Please install Git (https://git-scm.com/) and try again."
        ) from err
    except subprocess.TimeoutExpired as err:
        raise GitSizeError(
            f"Git command timed out after {timeout:.1f}s: git {' '.join(args)}"
        ) from err
    except OSError as err:
        raise GitSizeError(f"Failed to execute Git command: {err}") from err


def check_git_installed() -> str:
    """Verify that Git is installed and return its version string.

    Returns:
        Version string such as 'git version 2.40.0'.

    Raises:
        GitNotFoundError: If Git is not available.
    """
    proc = run_git_command(["--version"], timeout=10.0)
    if proc.returncode != 0:
        raise GitNotFoundError("Git command failed to execute properly.")
    return proc.stdout.strip()


def calculate_git_dir_size(git_dir: Path) -> int:
    """Safely calculate the on-disk storage size of the .git directory.

    Catches permission errors and missing files without crashing.

    Args:
        git_dir: Path to the .git directory.

    Returns:
        Total size in bytes of all readable files within the .git directory.
    """
    if not git_dir.exists():
        return 0

    if git_dir.is_file():
        # Submodule or git-worktree pointer file
        try:
            return git_dir.stat().st_size
        except OSError:
            return 0

    total_size = 0
    try:
        for root, _, files in os.walk(git_dir):
            for file_name in files:
                file_path = Path(root) / file_name
                try:
                    # Do not follow symlinks inside .git
                    stat = file_path.stat(follow_symlinks=False)
                    total_size += stat.st_size
                except (OSError, PermissionError):
                    continue
    except (OSError, PermissionError):
        pass

    return total_size


def detect_repository(target_path: Path | str = ".") -> RepositoryInfo:
    """Detect and validate a Git working tree at or above the given target path.

    Supports running from subdirectories inside a repository.

    Args:
        target_path: File system path to inspect (defaults to current directory).

    Returns:
        RepositoryInfo instance containing root, branch, empty/shallow status,
        and .git storage metrics.

    Raises:
        NotAGitRepositoryError: If path does not exist or is not inside a Git repository.
        GitNotFoundError: If git command is not installed.
    """
    target = Path(target_path).resolve()

    if not target.exists():
        raise NotAGitRepositoryError(f"Target path does not exist: {target}")

    # Determine starting working directory
    working_dir = target if target.is_dir() else target.parent

    # Check git installation first
    check_git_installed()

    # Query top-level root
    proc_root = run_git_command(["rev-parse", "--show-toplevel"], cwd=working_dir)
    if proc_root.returncode != 0:
        err_msg = proc_root.stderr.strip()
        if "not a git repository" in err_msg.lower():
            raise NotAGitRepositoryError(
                f"Directory '{target}' is not a valid Git repository (or any parent directory)."
            )
        raise NotAGitRepositoryError(
            err_msg or f"Could not detect Git repository at '{target}'."
        )

    root_path = Path(proc_root.stdout.strip()).resolve()

    # Check if repository is empty (HEAD points to a non-existent commit)
    proc_head = run_git_command(["rev-parse", "--verify", "HEAD"], cwd=root_path)
    is_empty = proc_head.returncode != 0

    # Determine current branch
    current_branch: str | None = None
    if is_empty:
        # For repositories without commits, extract unborn branch name
        proc_sym = run_git_command(["symbolic-ref", "--short", "HEAD"], cwd=root_path)
        if proc_sym.returncode == 0 and proc_sym.stdout.strip():
            current_branch = f"{proc_sym.stdout.strip()} (unborn)"
        else:
            current_branch = "HEAD (empty repository)"
    else:
        # Standard repository with commits
        proc_branch = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=root_path)
        if proc_branch.returncode == 0:
            branch_str = proc_branch.stdout.strip()
            if branch_str == "HEAD":
                # Detached HEAD state
                proc_short = run_git_command(["rev-parse", "--short", "HEAD"], cwd=root_path)
                short_hash = proc_short.stdout.strip() if proc_short.returncode == 0 else "unknown"
                current_branch = f"HEAD (detached at {short_hash})"
            else:
                current_branch = branch_str

    # Check if repository is shallow
    proc_shallow = run_git_command(["rev-parse", "--is-shallow-repository"], cwd=root_path)
    is_shallow = (
        proc_shallow.returncode == 0
        and proc_shallow.stdout.strip().lower() == "true"
    )

    # Determine .git size
    git_dir = root_path / ".git"
    git_dir_size = calculate_git_dir_size(git_dir)

    return RepositoryInfo(
        root_path=root_path,
        working_dir=working_dir,
        current_branch=current_branch,
        is_empty=is_empty,
        is_shallow=is_shallow,
        git_dir_size_bytes=git_dir_size,
    )

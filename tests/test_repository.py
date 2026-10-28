"""Tests for repository detection and Git integration."""

from pathlib import Path
import subprocess
from unittest.mock import patch
import pytest

from gitsize.exceptions import GitNotFoundError, NotAGitRepositoryError
from gitsize.repository import (
    calculate_git_dir_size,
    check_git_installed,
    detect_repository,
    run_git_command,
)


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """Create a temporary initialized Git repository with an initial commit."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)

    dummy_file = repo / "hello.txt"
    dummy_file.write_text("Hello GitSize!", encoding="utf-8")
    subprocess.run(["git", "add", "hello.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, check=True)
    return repo


@pytest.fixture
def empty_git_repo(tmp_path: Path) -> Path:
    """Create a temporary Git repository without any commits."""
    repo = tmp_path / "empty_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    return repo


def test_detect_repository_valid(temp_git_repo: Path):
    info = detect_repository(temp_git_repo)
    assert info.root_path.resolve() == temp_git_repo.resolve()
    assert not info.is_empty
    assert info.current_branch is not None
    assert info.git_dir_size_bytes > 0


def test_detect_repository_from_subdirectory(temp_git_repo: Path):
    subdir = temp_git_repo / "deep" / "nested" / "folder"
    subdir.mkdir(parents=True)
    info = detect_repository(subdir)
    assert info.root_path.resolve() == temp_git_repo.resolve()
    assert info.working_dir.resolve() == subdir.resolve()


def test_detect_repository_empty_repo(empty_git_repo: Path):
    info = detect_repository(empty_git_repo)
    assert info.root_path.resolve() == empty_git_repo.resolve()
    assert info.is_empty
    assert "unborn" in (info.current_branch or "").lower() or "empty" in (info.current_branch or "").lower()


def test_detect_repository_detached_head(temp_git_repo: Path):
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=temp_git_repo, capture_output=True, text=True, check=True)
    commit_sha = proc.stdout.strip()

    subprocess.run(["git", "checkout", commit_sha], cwd=temp_git_repo, capture_output=True, check=True)
    info = detect_repository(temp_git_repo)
    assert "detached" in (info.current_branch or "").lower()


def test_detect_repository_non_existent_path(tmp_path: Path):
    missing_path = tmp_path / "does_not_exist"
    with pytest.raises(NotAGitRepositoryError, match="Target path does not exist"):
        detect_repository(missing_path)


def test_detect_repository_not_a_git_repo(tmp_path: Path):
    plain_dir = tmp_path / "plain_dir"
    plain_dir.mkdir()
    with pytest.raises(NotAGitRepositoryError, match="not a valid Git repository"):
        detect_repository(plain_dir)


def test_check_git_installed_success():
    version_str = check_git_installed()
    assert "git version" in version_str.lower()


def test_git_not_found_error_raised():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(GitNotFoundError, match="Git is not installed"):
            run_git_command(["--version"])


def test_calculate_git_dir_size(temp_git_repo: Path):
    size = calculate_git_dir_size(temp_git_repo / ".git")
    assert size > 0

    missing_size = calculate_git_dir_size(temp_git_repo / "nonexistent_dir")
    assert missing_size == 0

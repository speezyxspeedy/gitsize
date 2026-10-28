"""Tests for Git history analysis, historical blob inspection, and deduplication."""

from pathlib import Path
import subprocess
import pytest

from gitsize.history import analyze_git_history
from gitsize.repository import RepositoryInfo


@pytest.fixture
def repo_with_history(tmp_path: Path) -> RepositoryInfo:
    """Create a repository with multiple commits, identical blobs, and deleted files."""
    root = tmp_path / "history_repo"
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)

    # Commit 1: Add a large file (3000 bytes) and a normal file (500 bytes)
    (root / "large_dataset.csv").write_text("x" * 3000, encoding="utf-8")
    (root / "readme.txt").write_text("Hello", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "Add dataset and readme"], cwd=root, check=True)

    # Commit 2: Add a duplicate of large_dataset.csv under another path (tests deduplication!)
    (root / "backup_dataset.csv").write_text("x" * 3000, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "Add backup copy"], cwd=root, check=True)

    # Commit 3: Delete large_dataset.csv from working tree (tests deleted file detection!)
    (root / "large_dataset.csv").unlink()
    subprocess.run(["git", "add", "-u"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "Delete dataset from working tree"], cwd=root, check=True)

    return RepositoryInfo(
        root_path=root,
        working_dir=root,
        current_branch="main",
        is_empty=False,
        is_shallow=False,
        git_dir_size_bytes=4096,
    )


def test_analyze_history_deduplication(repo_with_history: RepositoryInfo):
    analysis = analyze_git_history(repo_with_history, top_n=10)

    assert not analysis.is_empty
    # The 3000-byte content was committed under two paths, but shares the same blob hash!
    hashes = [b.blob_hash for b in analysis.top_blobs]
    assert len(hashes) == len(set(hashes)), "Duplicate blob hashes were returned!"

    # Verify largest blob is 3000 bytes
    largest_blob = analysis.top_blobs[0]
    assert largest_blob.size_bytes == 3000
    assert largest_blob.formatted_size == "2.93 KB"
    assert largest_blob.commit_ref is not None


def test_analyze_history_detects_deleted_working_tree_file(repo_with_history: RepositoryInfo):
    # Commit a distinct file and delete it
    root = repo_with_history.root_path
    ghost_file = root / "ghost.log"
    ghost_file.write_text("z" * 5000, encoding="utf-8")
    subprocess.run(["git", "add", "ghost.log"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "Add ghost log"], cwd=root, check=True)

    ghost_file.unlink()
    subprocess.run(["git", "add", "-u"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "Remove ghost log"], cwd=root, check=True)

    analysis = analyze_git_history(repo_with_history, top_n=10)
    ghost_blob = next(b for b in analysis.top_blobs if "ghost.log" in b.path)

    assert ghost_blob.size_bytes == 5000
    assert ghost_blob.is_deleted_in_working_tree is True


def test_analyze_history_empty_repo(tmp_path: Path):
    empty_root = tmp_path / "empty_history_repo"
    empty_root.mkdir()
    subprocess.run(["git", "init"], cwd=empty_root, check=True, capture_output=True)

    repo_info = RepositoryInfo(
        root_path=empty_root,
        working_dir=empty_root,
        current_branch="main",
        is_empty=True,
        is_shallow=False,
        git_dir_size_bytes=100,
    )

    analysis = analyze_git_history(repo_info)
    assert analysis.is_empty is True
    assert len(analysis.top_blobs) == 0
    assert any("no commits" in note.lower() for note in analysis.notes)


def test_analyze_history_top_n_limit(repo_with_history: RepositoryInfo):
    analysis = analyze_git_history(repo_with_history, top_n=1)
    assert len(analysis.top_blobs) == 1

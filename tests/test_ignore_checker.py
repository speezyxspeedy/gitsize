"""Tests for .gitignore recommendations and security guards."""

from pathlib import Path
import subprocess
import pytest

from gitsize.ignore_checker import (
    check_gitignore_recommendations,
    read_existing_gitignore_patterns,
)
from gitsize.repository import RepositoryInfo


@pytest.fixture
def repo_with_artifacts(tmp_path: Path) -> RepositoryInfo:
    """Create a test repository containing various unignored artifacts."""
    root = tmp_path / "artifact_repo"
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=root, check=True)

    # Create unignored artifacts
    venv_dir = root / ".venv"
    venv_dir.mkdir()
    (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin", encoding="utf-8")

    pycache = root / "src" / "__pycache__"
    pycache.mkdir(parents=True)
    (pycache / "app.cpython-312.pyc").write_bytes(b"\x00\x01\x02\x03")

    env_file = root / ".env"
    env_file.write_text("SUPER_SECRET_KEY=1234567890abcdef\nAPI_TOKEN=xyz", encoding="utf-8")

    node_modules = root / "node_modules"
    node_modules.mkdir()
    (node_modules / "pkg.json").write_text("{}", encoding="utf-8")

    return RepositoryInfo(
        root_path=root,
        working_dir=root,
        current_branch="main",
        is_empty=True,
        is_shallow=False,
        git_dir_size_bytes=512,
    )


def test_missing_ignore_rules_detected(repo_with_artifacts: RepositoryInfo):
    recommendations = check_gitignore_recommendations(repo_with_artifacts)

    patterns = [r.suggested_pattern for r in recommendations]
    assert ".venv/" in patterns
    assert "__pycache__/" in patterns
    assert ".env" in patterns
    assert "node_modules/" in patterns

    # Check reason explanations are informative
    for r in recommendations:
        assert len(r.reason) > 20
        assert r.category != ""


def test_already_ignored_patterns_not_suggested(repo_with_artifacts: RepositoryInfo):
    root = repo_with_artifacts.root_path
    gitignore = root / ".gitignore"
    gitignore.write_text(".venv/\n.env\n", encoding="utf-8")

    # Add and commit .gitignore so git check-ignore respects it
    subprocess.run(["git", "add", ".gitignore"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "Add gitignore"], cwd=root, check=True)

    # Re-detect repo info with updated commit state
    updated_repo_info = RepositoryInfo(
        root_path=root,
        working_dir=root,
        current_branch="main",
        is_empty=False,
        is_shallow=False,
        git_dir_size_bytes=512,
    )

    recommendations = check_gitignore_recommendations(updated_repo_info)
    patterns = [r.suggested_pattern for r in recommendations]

    # .venv/ and .env must NOT be suggested since they are already ignored
    assert ".venv/" not in patterns
    assert ".env" not in patterns

    # __pycache__/ and node_modules/ are still unignored and should be suggested
    assert "__pycache__/" in patterns
    assert "node_modules/" in patterns


def test_duplicate_suggestions_avoided(repo_with_artifacts: RepositoryInfo):
    # Add another nested __pycache__
    root = repo_with_artifacts.root_path
    extra_cache = root / "tests" / "__pycache__"
    extra_cache.mkdir(parents=True)
    (extra_cache / "test.cpython-312.pyc").write_bytes(b"\x00")

    recommendations = check_gitignore_recommendations(repo_with_artifacts)
    pycache_recs = [r for r in recommendations if r.suggested_pattern == "__pycache__/"]
    assert len(pycache_recs) == 1  # Deduplicated into a single recommendation


def test_secrets_in_env_file_never_exposed(repo_with_artifacts: RepositoryInfo):
    """Verify secret token values are NEVER leaked in recommendation output or reasons."""
    recommendations = check_gitignore_recommendations(repo_with_artifacts)
    env_rec = next(r for r in recommendations if r.suggested_pattern == ".env")

    assert "SUPER_SECRET_KEY" not in env_rec.reason
    assert "1234567890abcdef" not in env_rec.reason
    assert "API_TOKEN" not in env_rec.reason
    assert "xyz" not in env_rec.reason


def test_ignore_checker_never_modifies_files(repo_with_artifacts: RepositoryInfo):
    root = repo_with_artifacts.root_path
    gitignore = root / ".gitignore"
    if gitignore.exists():
        initial_content = gitignore.read_text(encoding="utf-8")
    else:
        initial_content = None

    _ = check_gitignore_recommendations(repo_with_artifacts)

    if initial_content is None:
        assert not gitignore.exists(), ".gitignore should not be automatically created"
    else:
        assert gitignore.read_text(encoding="utf-8") == initial_content, ".gitignore was modified"


def test_read_existing_gitignore_patterns_handles_comments_and_blank_lines(tmp_path: Path):
    root = tmp_path / "test_repo"
    root.mkdir()
    gitignore = root / ".gitignore"
    gitignore.write_text("# This is a comment\n\n.venv/\nnode_modules\n\n# Another comment\n", encoding="utf-8")

    patterns = read_existing_gitignore_patterns(root)
    assert ".venv" in patterns
    assert ".venv/" in patterns
    assert "node_modules" in patterns
    assert "# This is a comment" not in patterns

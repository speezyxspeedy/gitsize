"""Tests for working-tree file scanner, safety guards, and size aggregation."""

import hashlib
import os
from pathlib import Path
import subprocess
from unittest.mock import patch
import pytest

from gitsize.repository import RepositoryInfo
from gitsize.scanner import (
    ScanWarning,
    is_excluded,
    scan_working_tree,
)


@pytest.fixture
def sample_repo(tmp_path: Path) -> RepositoryInfo:
    """Create a test repository structure with varied file sizes and types."""
    root = tmp_path / "sample_repo"
    root.mkdir()
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)

    # Create dummy files
    (root / "small.txt").write_text("a" * 100, encoding="utf-8")
    (root / "medium.py").write_text("b" * 1000, encoding="utf-8")
    (root / "large.bin").write_bytes(b"c" * 5000)

    # Nested files
    nested = root / "src" / "pkg"
    nested.mkdir(parents=True)
    (nested / "module.py").write_text("d" * 2000, encoding="utf-8")
    (nested / "config.json").write_text("e" * 300, encoding="utf-8")

    # Excluded folder files
    node_modules = root / "node_modules" / "dep"
    node_modules.mkdir(parents=True)
    (node_modules / "huge.js").write_text("x" * 20000, encoding="utf-8")

    venv_dir = root / ".venv" / "lib"
    venv_dir.mkdir(parents=True)
    (venv_dir / "site.py").write_text("y" * 15000, encoding="utf-8")

    return RepositoryInfo(
        root_path=root,
        working_dir=root,
        current_branch="main",
        is_empty=False,
        is_shallow=False,
        git_dir_size_bytes=1024,
    )


def test_scan_largest_files_and_top_n(sample_repo: RepositoryInfo):
    result = scan_working_tree(sample_repo, top_n=3)

    assert result.total_files == 5  # small.txt, medium.py, large.bin, module.py, config.json
    assert len(result.largest_files) == 3

    # Rank 1: large.bin (5000 B)
    assert result.largest_files[0].path.name == "large.bin"
    assert result.largest_files[0].size_bytes == 5000

    # Rank 2: module.py (2000 B)
    assert result.largest_files[1].path.name == "module.py"
    assert result.largest_files[1].size_bytes == 2000

    # Rank 3: medium.py (1000 B)
    assert result.largest_files[2].path.name == "medium.py"
    assert result.largest_files[2].size_bytes == 1000


def test_scan_file_type_aggregation(sample_repo: RepositoryInfo):
    result = scan_working_tree(sample_repo)

    ext_map = {item.extension: item for item in result.file_type_stats}

    assert ".bin" in ext_map
    assert ext_map[".bin"].count == 1
    assert ext_map[".bin"].total_size_bytes == 5000

    assert ".py" in ext_map
    assert ext_map[".py"].count == 2
    assert ext_map[".py"].total_size_bytes == 3000

    assert ".txt" in ext_map
    assert ext_map[".txt"].count == 1
    assert ext_map[".txt"].total_size_bytes == 100

    assert ".json" in ext_map
    assert ext_map[".json"].count == 1
    assert ext_map[".json"].total_size_bytes == 300


def test_scan_exclusions_working(sample_repo: RepositoryInfo):
    # By default, node_modules and .venv are excluded
    result_default = scan_working_tree(sample_repo)
    paths_default = [f.relative_path for f in result_default.largest_files]
    assert not any("node_modules" in p for p in paths_default)
    assert not any(".venv" in p for p in paths_default)

    # Custom exclusion: exclude src folder
    result_custom = scan_working_tree(sample_repo, user_excludes=["src"])
    paths_custom = [f.relative_path for f in result_custom.largest_files]
    assert not any(p.startswith("src") for p in paths_custom)


def test_is_excluded_helper():
    assert is_excluded(Path("node_modules/package.json"), [".git", "node_modules"])
    assert is_excluded(Path("backend/__pycache__/app.pyc"), ["__pycache__"])
    assert is_excluded(Path("dist/bundle.js"), ["dist"])
    assert not is_excluded(Path("src/main.py"), ["node_modules", "dist"])


def test_scan_read_only_confirmation(sample_repo: RepositoryInfo):
    """Verify scanning strictly does NOT modify file contents, hashes, or timestamps."""
    files_before: dict[Path, tuple[str, float]] = {}
    for p in sample_repo.root_path.rglob("*"):
        if p.is_file():
            content = p.read_bytes()
            h = hashlib.sha256(content).hexdigest()
            mtime = p.stat().st_mtime
            files_before[p] = (h, mtime)

    # Perform scan
    result = scan_working_tree(sample_repo, top_n=10)
    assert result.total_files > 0

    # Verify no file was altered
    for p, (expected_hash, expected_mtime) in files_before.items():
        assert p.exists()
        current_hash = hashlib.sha256(p.read_bytes()).hexdigest()
        current_mtime = p.stat().st_mtime
        assert current_hash == expected_hash, f"File content altered during scan: {p}"
        assert current_mtime == expected_mtime, f"File timestamp altered during scan: {p}"


def test_scan_handles_permission_errors_gracefully(sample_repo: RepositoryInfo):
    with patch("os.scandir", side_effect=PermissionError("Simulated permission denied")):
        result = scan_working_tree(sample_repo)
        assert len(result.warnings) > 0
        assert any("Permission denied" in w.reason for w in result.warnings)


def test_scan_handles_disappearing_files_gracefully(sample_repo: RepositoryInfo):
    with patch("os.DirEntry.stat", side_effect=FileNotFoundError("Simulated vanished file")):
        result = scan_working_tree(sample_repo)
        assert len(result.warnings) > 0
        assert any("disappeared" in w.reason.lower() for w in result.warnings)


def test_scan_symlink_pointing_outside_repository(tmp_path: Path):
    """Verify symlinks pointing outside repository boundary are skipped with a warning."""
    outside_dir = tmp_path / "outside_dir"
    outside_dir.mkdir()
    outside_secret = outside_dir / "secret.txt"
    outside_secret.write_text("secret outside repo", encoding="utf-8")

    repo_root = tmp_path / "safe_repo"
    repo_root.mkdir()
    subprocess.run(["git", "init"], cwd=repo_root, check=True, capture_output=True)

    link_path = repo_root / "leak_link.txt"
    try:
        os.symlink(outside_secret, link_path)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation not permitted in this Windows environment.")

    repo_info = RepositoryInfo(
        root_path=repo_root,
        working_dir=repo_root,
        current_branch="main",
        is_empty=True,
        is_shallow=False,
        git_dir_size_bytes=512,
    )

    result = scan_working_tree(repo_info)
    assert result.total_files == 0  # Should NOT scan the outside file!
    assert len(result.warnings) > 0
    assert any("outside repository boundary" in w.reason for w in result.warnings)

"""Tests for report generation (Terminal, Markdown, JSON) and file saving."""

import json
from pathlib import Path
import pytest

from gitsize.exceptions import ReportExistsError
from gitsize.history import GitHistoryAnalysis, HistoricalBlob
from gitsize.ignore_checker import IgnoreRecommendation
from gitsize.report import (
    render_json_report,
    render_markdown_report,
    render_terminal_report,
    write_report_file,
)
from gitsize.repository import RepositoryInfo
from gitsize.scanner import (
    FileInfo,
    FileTypeStat,
    ScanWarning,
    WorkingTreeScanResult,
)


@pytest.fixture
def mock_scan_result(tmp_path: Path) -> WorkingTreeScanResult:
    repo = RepositoryInfo(
        root_path=tmp_path / "mock_repo",
        working_dir=tmp_path / "mock_repo",
        current_branch="main",
        is_empty=False,
        is_shallow=False,
        git_dir_size_bytes=1024 * 50,
    )
    largest_files = [
        FileInfo(
            path=repo.root_path / "app.py",
            relative_path="app.py",
            size_bytes=10240,
            extension=".py",
        ),
        FileInfo(
            path=repo.root_path / "data.csv",
            relative_path="data.csv",
            size_bytes=2048,
            extension=".csv",
        ),
    ]
    file_type_stats = [
        FileTypeStat(extension=".py", count=1, total_size_bytes=10240, percentage=83.33),
        FileTypeStat(extension=".csv", count=1, total_size_bytes=2048, percentage=16.67),
    ]
    warnings = [
        ScanWarning(path="locked.log", reason="Permission denied"),
    ]
    return WorkingTreeScanResult(
        repository_info=repo,
        total_files=2,
        total_size_bytes=12288,
        largest_files=largest_files,
        file_type_stats=file_type_stats,
        warnings=warnings,
        excluded_patterns=[".git", "node_modules", ".venv"],
        git_dir_size_bytes=1024 * 50,
    )


@pytest.fixture
def mock_recommendations() -> list[IgnoreRecommendation]:
    return [
        IgnoreRecommendation(
            suggested_pattern=".venv/",
            category="Virtual Environments",
            detected_path=".venv",
            reason="Contains machine-specific binaries",
            matched_files_count=15,
            total_size_bytes=50000,
        )
    ]


@pytest.fixture
def mock_history_analysis() -> GitHistoryAnalysis:
    return GitHistoryAnalysis(
        is_empty=False,
        is_shallow=False,
        total_blobs_found=1,
        total_blob_bytes=8192,
        top_blobs=[
            HistoricalBlob(
                blob_hash="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
                short_hash="a1b2c3d4",
                size_bytes=8192,
                path="old_data.bin",
                commit_ref="abc1234 Initial data",
                is_deleted_in_working_tree=True,
            )
        ],
        notes=["Historical sizes are uncompressed."],
    )


def test_render_terminal_report(mock_scan_result, mock_recommendations, mock_history_analysis):
    report = render_terminal_report(
        mock_scan_result,
        recommendations=mock_recommendations,
        history_analysis=mock_history_analysis,
    )
    assert "GitSize" in report
    assert "app.py" in report
    assert "data.csv" in report
    assert ".venv/" in report
    assert "old_data.bin" in report
    assert "Permission denied" in report


def test_render_markdown_report_sections(mock_scan_result, mock_recommendations, mock_history_analysis):
    md = render_markdown_report(
        mock_scan_result,
        recommendations=mock_recommendations,
        history_analysis=mock_history_analysis,
    )
    # Check all required section headers
    assert "# GitSize Repository Storage Analysis Report" in md
    assert "## 1. Repository Information" in md
    assert "## 2. Working-Tree Size Summary" in md
    assert "## 3. Top 2 Largest Files (Working Tree)" in md
    assert "## 4. File-Type Breakdown" in md
    assert "## 5. .gitignore Recommendations" in md
    assert "## 6. Git History Findings" in md
    assert "## 7. Scan Warnings and Limitations" in md

    # Check content items
    assert "`app.py`" in md
    assert "`.venv/`" in md
    assert "`old_data.bin`" in md
    assert "Permission denied" in md


def test_render_json_report_validity(mock_scan_result, mock_recommendations, mock_history_analysis):
    raw_json = render_json_report(
        mock_scan_result,
        recommendations=mock_recommendations,
        history_analysis=mock_history_analysis,
    )
    data = json.loads(raw_json)

    assert data["tool"] == "gitsize"
    assert "version" in data
    assert "timestamp" in data
    assert "repository" in data
    assert "working_tree" in data
    assert len(data["working_tree"]["largest_files"]) == 2
    assert len(data["working_tree"]["file_type_breakdown"]) == 2
    assert len(data["ignore_recommendations"]) == 1
    assert data["history"]["total_blobs_found"] == 1
    assert len(data["warnings"]) == 1


def test_write_report_file_safely(tmp_path: Path):
    target = tmp_path / "reports" / "summary.md"
    content = "# Test Report"

    # 1. Normal save to new file
    written = write_report_file(content, target, force=False)
    assert written.exists()
    assert written.read_text(encoding="utf-8") == content

    # 2. Refuses overwrite without force
    with pytest.raises(ReportExistsError, match="already exists"):
        write_report_file("Overwritten", target, force=False)

    # 3. Permits overwrite with force=True
    write_report_file("Overwritten Content", target, force=True)
    assert target.read_text(encoding="utf-8") == "Overwritten Content"


def test_render_html_report(mock_scan_result, mock_recommendations, mock_history_analysis):
    from gitsize.report import render_html_report

    html = render_html_report(
        mock_scan_result,
        recommendations=mock_recommendations,
        history_analysis=mock_history_analysis,
    )
    assert "<!DOCTYPE html>" in html
    assert "GitSize" in html
    assert "app.py" in html
    assert ".venv/" in html
    assert "old_data.bin" in html
    assert "initDashboard" in html


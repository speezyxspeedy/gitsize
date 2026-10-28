"""Report generation for Terminal, Markdown, and JSON formats."""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Sequence

from gitsize import __version__
from gitsize.exceptions import ReportExistsError
from gitsize.formatting import format_bytes, format_table
from gitsize.history import GitHistoryAnalysis
from gitsize.ignore_checker import IgnoreRecommendation
from gitsize.scanner import WorkingTreeScanResult


def write_report_file(content: str, output_path: Path | str, force: bool = False) -> Path:
    """Safely write report content to an output file.

    Guarantees:
    - Never overwrites an existing file unless force=True.
    - Creates necessary parent directories.
    - Writes UTF-8 encoded text.

    Args:
        content: Formatted report text (Markdown, JSON, etc.).
        output_path: Target filesystem path.
        force: Whether to overwrite an existing file.

    Returns:
        Resolved Path to the written file.

    Raises:
        ReportExistsError: If output path exists and force is False.
    """
    path = Path(output_path).resolve()
    if path.exists() and not force:
        raise ReportExistsError(
            f"Output file '{path}' already exists. Pass --force to overwrite."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def render_terminal_report(
    scan_result: WorkingTreeScanResult,
    recommendations: Sequence[IgnoreRecommendation] | None = None,
    history_analysis: GitHistoryAnalysis | None = None,
) -> str:
    """Format an aesthetically aligned, readable plain-text report for terminal display."""
    lines: list[str] = []
    repo = scan_result.repository_info

    # Banner
    lines.append("=" * 72)
    lines.append(f"  GitSize v{__version__} - Repository Storage Analysis")
    lines.append("=" * 72)

    # Repository & Working Tree Summary
    branch_display = repo.current_branch or "Unknown"
    lines.append(f"Repository Root    : {repo.root_path}")
    lines.append(f"Current Branch     : {branch_display}")
    lines.append(
        f"Working Tree Size  : {scan_result.formatted_total_size} ({scan_result.total_files:,} files scanned)"
    )
    lines.append(
        f"Git Metadata (.git): {scan_result.formatted_git_dir_size} (local repository database)"
    )
    if scan_result.excluded_patterns:
        lines.append(f"Exclusions Applied : {', '.join(scan_result.excluded_patterns)}")
    lines.append("")

    # Largest Files
    lines.append(f"--- Top {len(scan_result.largest_files)} Largest Files (Working Tree) ---")
    if scan_result.largest_files:
        headers = ["Rank", "Path", "Size", "Bytes"]
        rows = []
        for idx, item in enumerate(scan_result.largest_files, 1):
            rows.append(
                [
                    f"#{idx}",
                    item.relative_path,
                    item.formatted_size,
                    f"{item.size_bytes:,} B",
                ]
            )
        lines.append(format_table(headers, rows, alignments=["<", "<", ">", ">"]))
    else:
        lines.append("No files found in working tree.")
    lines.append("")

    # File Type Statistics
    lines.append("--- Storage by File Type ---")
    if scan_result.file_type_stats:
        headers = ["Extension", "Count", "Total Size", "% Total"]
        rows = []
        for stat in scan_result.file_type_stats[:10]:
            rows.append(
                [
                    stat.extension,
                    f"{stat.count:,}",
                    stat.formatted_size,
                    f"{stat.percentage:.1f}%",
                ]
            )
        lines.append(format_table(headers, rows, alignments=["<", ">", ">", ">"]))
        if len(scan_result.file_type_stats) > 10:
            lines.append(
                f"... and {len(scan_result.file_type_stats) - 10} additional file types."
            )
    else:
        lines.append("No file extensions detected.")
    lines.append("")

    # .gitignore Recommendations
    if recommendations is not None:
        lines.append("--- .gitignore Recommendations ---")
        if recommendations:
            headers = ["Suggested Rule", "Category", "Detected At", "Unignored Size"]
            rows = []
            for rec in recommendations:
                rows.append(
                    [
                        rec.suggested_pattern,
                        rec.category,
                        rec.detected_path,
                        rec.formatted_size,
                    ]
                )
            lines.append(format_table(headers, rows, alignments=["<", "<", "<", ">"]))
            lines.append("")
            lines.append("Recommendations are advisory. Review carefully before adding to .gitignore.")
        else:
            lines.append("No common missing .gitignore patterns detected. Working tree looks clean!")
        lines.append("")

    # Git History Analysis
    if history_analysis is not None:
        lines.append("--- Git History Storage Findings ---")
        for note in history_analysis.notes:
            lines.append(f"* {note}")
        lines.append("")

        if history_analysis.top_blobs:
            headers = ["Blob SHA", "Historical Path", "Size", "Commit Ref", "Status"]
            rows = []
            for blob in history_analysis.top_blobs:
                status = "Deleted in WT" if blob.is_deleted_in_working_tree else "Active in WT"
                commit = blob.commit_ref or "(unknown)"
                rows.append(
                    [
                        blob.short_hash,
                        blob.path,
                        blob.formatted_size,
                        commit,
                        status,
                    ]
                )
            lines.append(format_table(headers, rows, alignments=["<", "<", ">", "<", "<"]))
        else:
            lines.append("No historical blobs found.")
        lines.append("")

    # Scan Warnings
    if scan_result.warnings:
        lines.append("--- Scan Warnings & Limitations ---")
        for warn in scan_result.warnings[:10]:
            lines.append(f"! [{warn.path}] {warn.reason}")
        if len(scan_result.warnings) > 10:
            lines.append(f"... and {len(scan_result.warnings) - 10} additional warnings.")
        lines.append("")

    lines.append("=" * 72)
    return "\n".join(lines)


def render_markdown_report(
    scan_result: WorkingTreeScanResult,
    recommendations: Sequence[IgnoreRecommendation] | None = None,
    history_analysis: GitHistoryAnalysis | None = None,
) -> str:
    """Generate a GitHub Flavored Markdown report suitable for documentation or portfolios."""
    lines: list[str] = []
    repo = scan_result.repository_info
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines.append("# GitSize Repository Storage Analysis Report")
    lines.append("")
    lines.append(f"> Generated by **GitSize v{__version__}** on `{timestamp}`")
    lines.append("")

    # Section 1: Repository Information
    lines.append("## 1. Repository Information")
    lines.append("")
    lines.append("| Property | Value |")
    lines.append("| :--- | :--- |")
    lines.append(f"| **Repository Root** | `{repo.root_path}` |")
    lines.append(f"| **Current Branch** | `{repo.current_branch or 'N/A'}` |")
    lines.append(f"| **Empty Repository** | `{'Yes' if repo.is_empty else 'No'}` |")
    lines.append(f"| **Shallow Clone** | `{'Yes' if repo.is_shallow else 'No'}` |")
    lines.append(f"| **Git Metadata Size (`.git`)** | `{scan_result.formatted_git_dir_size}` ({repo.git_dir_size_bytes:,} bytes) |")
    lines.append("")

    # Section 2: Working-Tree Size Summary
    lines.append("## 2. Working-Tree Size Summary")
    lines.append("")
    lines.append(f"- **Total Scanned Files**: {scan_result.total_files:,}")
    lines.append(f"- **Total Working Tree Storage**: {scan_result.formatted_total_size} ({scan_result.total_size_bytes:,} bytes)")
    if scan_result.excluded_patterns:
        lines.append(f"- **Exclusions Applied**: `{', '.join(scan_result.excluded_patterns)}`")
    lines.append("")
    lines.append("> **Note**: Working-tree storage represents the active uncompressed files currently checked out on disk. This is distinct from historical Git objects packed in `.git/`.")
    lines.append("")

    # Section 3: Largest Files
    lines.append(f"## 3. Top {len(scan_result.largest_files)} Largest Files (Working Tree)")
    lines.append("")
    if scan_result.largest_files:
        lines.append("| Rank | Relative Path | Size | Bytes |")
        lines.append("| :---: | :--- | :---: | ---: |")
        for idx, item in enumerate(scan_result.largest_files, 1):
            lines.append(f"| #{idx} | `{item.relative_path}` | {item.formatted_size} | {item.size_bytes:,} |")
    else:
        lines.append("_No files were scanned in the working tree._")
    lines.append("")

    # Section 4: File-Type Breakdown
    lines.append("## 4. File-Type Breakdown")
    lines.append("")
    if scan_result.file_type_stats:
        lines.append("| Extension | File Count | Total Size | % of Working Tree |")
        lines.append("| :--- | ---: | :---: | ---: |")
        for stat in scan_result.file_type_stats:
            lines.append(
                f"| `{stat.extension}` | {stat.count:,} | {stat.formatted_size} | {stat.percentage:.1f}% |"
            )
    else:
        lines.append("_No file extension statistics available._")
    lines.append("")

    # Section 5: .gitignore Recommendations
    lines.append("## 5. .gitignore Recommendations")
    lines.append("")
    if recommendations is not None:
        if recommendations:
            lines.append("| Suggested Rule | Category | Detected Path | Impact / Reason |")
            lines.append("| :--- | :--- | :--- | :--- |")
            for rec in recommendations:
                lines.append(
                    f"| `{rec.suggested_pattern}` | {rec.category} | `{rec.detected_path}` ({rec.formatted_size}) | {rec.reason} |"
                )
            lines.append("")
            lines.append("> **Advisory**: Suggestions are non-destructive recommendations. Inspect each rule before adding it to your `.gitignore` file.")
        else:
            lines.append("No missing standard `.gitignore` patterns were detected.")
    else:
        lines.append("_Ignore pattern check was not requested for this scan._")
    lines.append("")

    # Section 6: Optional Git-History Findings
    if history_analysis is not None:
        lines.append("## 6. Git History Findings")
        lines.append("")
        for note in history_analysis.notes:
            lines.append(f"- {note}")
        lines.append("")
        if history_analysis.top_blobs:
            lines.append("| Blob SHA | Historical Path | Object Size | Commit Reference | Working Tree Status |")
            lines.append("| :---: | :--- | :---: | :--- | :---: |")
            for blob in history_analysis.top_blobs:
                status = "Deleted" if blob.is_deleted_in_working_tree else "Active"
                commit = blob.commit_ref or "N/A"
                lines.append(
                    f"| `{blob.short_hash}` | `{blob.path}` | {blob.formatted_size} | {commit} | {status} |"
                )
        else:
            lines.append("_No historical blob records found._")
        lines.append("")

    # Section 7: Scan Warnings and Limitations
    lines.append("## 7. Scan Warnings and Limitations")
    lines.append("")
    if scan_result.warnings:
        lines.append(f"Encountered **{len(scan_result.warnings)}** warning(s) during scanning:")
        lines.append("")
        for warn in scan_result.warnings:
            lines.append(f"- `{warn.path}`: {warn.reason}")
    else:
        lines.append("No permission errors, cyclic symbolic links, or missing files occurred during scan.")
    lines.append("")

    return "\n".join(lines)


def build_json_data(
    scan_result: WorkingTreeScanResult,
    recommendations: Sequence[IgnoreRecommendation] | None = None,
    history_analysis: GitHistoryAnalysis | None = None,
) -> dict[str, Any]:
    """Serialize scan results, recommendations, and history into a structured dictionary."""
    repo = scan_result.repository_info
    timestamp = datetime.now(timezone.utc).isoformat()

    data: dict[str, Any] = {
        "tool": "gitsize",
        "version": __version__,
        "timestamp": timestamp,
        "repository": {
            "root_path": str(repo.root_path),
            "working_dir": str(repo.working_dir),
            "current_branch": repo.current_branch,
            "is_empty": repo.is_empty,
            "is_shallow": repo.is_shallow,
            "git_dir_size_bytes": repo.git_dir_size_bytes,
            "formatted_git_dir_size": scan_result.formatted_git_dir_size,
        },
        "working_tree": {
            "total_files": scan_result.total_files,
            "total_size_bytes": scan_result.total_size_bytes,
            "formatted_total_size": scan_result.formatted_total_size,
            "excluded_patterns": scan_result.excluded_patterns,
            "largest_files": [
                {
                    "relative_path": f.relative_path,
                    "size_bytes": f.size_bytes,
                    "formatted_size": f.formatted_size,
                    "extension": f.extension,
                }
                for f in scan_result.largest_files
            ],
            "file_type_breakdown": [
                {
                    "extension": s.extension,
                    "count": s.count,
                    "total_size_bytes": s.total_size_bytes,
                    "formatted_size": s.formatted_size,
                    "percentage": s.percentage,
                }
                for s in scan_result.file_type_stats
            ],
        },
        "warnings": [
            {"path": w.path, "reason": w.reason} for w in scan_result.warnings
        ],
    }

    if recommendations is not None:
        data["ignore_recommendations"] = [
            {
                "suggested_pattern": r.suggested_pattern,
                "category": r.category,
                "detected_path": r.detected_path,
                "reason": r.reason,
                "matched_files_count": r.matched_files_count,
                "total_size_bytes": r.total_size_bytes,
                "formatted_size": r.formatted_size,
            }
            for r in recommendations
        ]

    if history_analysis is not None:
        data["history"] = {
            "is_empty": history_analysis.is_empty,
            "is_shallow": history_analysis.is_shallow,
            "total_blobs_found": history_analysis.total_blobs_found,
            "total_blob_bytes": history_analysis.total_blob_bytes,
            "formatted_total_size": history_analysis.formatted_total_size,
            "notes": history_analysis.notes,
            "top_blobs": [
                {
                    "blob_hash": b.blob_hash,
                    "short_hash": b.short_hash,
                    "size_bytes": b.size_bytes,
                    "formatted_size": b.formatted_size,
                    "path": b.path,
                    "commit_ref": b.commit_ref,
                    "is_deleted_in_working_tree": b.is_deleted_in_working_tree,
                }
                for b in history_analysis.top_blobs
            ],
        }

    return data


def render_json_report(
    scan_result: WorkingTreeScanResult,
    recommendations: Sequence[IgnoreRecommendation] | None = None,
    history_analysis: GitHistoryAnalysis | None = None,
    indent: int = 2,
) -> str:
    """Produce formatted JSON report string."""
    data = build_json_data(scan_result, recommendations, history_analysis)
    return json.dumps(data, indent=indent)


def render_html_report(
    scan_result: WorkingTreeScanResult,
    recommendations: Sequence[IgnoreRecommendation] | None = None,
    history_analysis: GitHistoryAnalysis | None = None,
) -> str:
    """Produce a self-contained interactive HTML dashboard report."""
    from gitsize.web import generate_dashboard_html
    data = build_json_data(scan_result, recommendations, history_analysis)
    return generate_dashboard_html(data)


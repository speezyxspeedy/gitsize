"""Command-line interface for GitSize."""

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from gitsize import __version__
from gitsize.exceptions import (
    EmptyRepositoryError,
    GitNotFoundError,
    GitSizeError,
    NotAGitRepositoryError,
    ReportExistsError,
    ScanError,
)
from gitsize.formatting import format_table
from gitsize.history import analyze_git_history
from gitsize.ignore_checker import check_gitignore_recommendations
from gitsize.report import (
    render_json_report,
    render_markdown_report,
    render_terminal_report,
    write_report_file,
)
from gitsize.repository import detect_repository
from gitsize.scanner import scan_working_tree


def parse_exclude_argument(exclude_str: str | None) -> list[str]:
    """Parse comma- or semicolon-separated exclude strings into a clean list."""
    if not exclude_str:
        return []
    parts = []
    for item in exclude_str.replace(";", ",").split(","):
        cleaned = item.strip()
        if cleaned:
            parts.append(cleaned)
    return parts


def create_parser() -> argparse.ArgumentParser:
    """Build and configure the main argument parser for GitSize."""
    parser = argparse.ArgumentParser(
        prog="gitsize",
        description=(
            "GitSize - Git Repository Storage Analyzer.\n"
            "Analyze working-tree files, historical Git objects, and .gitignore hygiene."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"GitSize v{__version__}",
        help="Show program version and exit.",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: scan
    scan_parser = subparsers.add_parser(
        "scan",
        help="Analyze working-tree storage and common .gitignore recommendations.",
        description="Scan repository files, report largest files, file-type statistics, and warnings.",
    )
    scan_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to repository or subdirectory (default: current directory).",
    )
    scan_parser.add_argument(
        "--top",
        type=int,
        default=10,
        metavar="N",
        help="Number of largest files to report (default: 10).",
    )
    scan_parser.add_argument(
        "--exclude",
        type=str,
        default=None,
        metavar="PATTERNS",
        help="Comma-separated directories or patterns to exclude (e.g. 'node_modules,.venv,dist').",
    )
    scan_parser.add_argument(
        "--no-default-excludes",
        action="store_true",
        help="Disable built-in default exclusions (.venv, node_modules, dist, etc.).",
    )
    scan_parser.add_argument(
        "--include-history",
        action="store_true",
        help="Include historical Git blob analysis in the scan report.",
    )
    scan_parser.add_argument(
        "--format",
        choices=["terminal", "markdown", "json", "html"],
        default="terminal",
        help="Output report format (default: terminal).",
    )
    scan_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        metavar="FILE",
        help="Save report to specified file path instead of stdout.",
    )
    scan_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing output report file if it already exists.",
    )

    # Command: web
    web_parser = subparsers.add_parser(
        "web",
        help="Launch interactive web dashboard in browser.",
        description="Serve an interactive, visual GitSize storage dashboard locally.",
    )
    web_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to repository or subdirectory (default: current directory).",
    )
    web_parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Local HTTP server port (default: 8080).",
    )
    web_parser.add_argument(
        "--no-browse",
        action="store_true",
        help="Do not automatically launch web browser.",
    )

    # Command: ignore-check
    ignore_parser = subparsers.add_parser(
        "ignore-check",
        help="Audit repository for missing .gitignore rules.",
        description="Detect common development artifacts (caches, .env, virtualenvs) that should be ignored.",
    )
    ignore_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to repository or subdirectory (default: current directory).",
    )
    ignore_parser.add_argument(
        "--format",
        choices=["terminal", "markdown", "json"],
        default="terminal",
        help="Output report format (default: terminal).",
    )
    ignore_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        metavar="FILE",
        help="Save report to specified file path instead of stdout.",
    )
    ignore_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing output report file if it already exists.",
    )

    # Command: history
    history_parser = subparsers.add_parser(
        "history",
        help="Analyze Git historical object storage and large deleted blobs.",
        description="Inspect Git object database for large historical commits and uncompressed blobs.",
    )
    history_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to repository or subdirectory (default: current directory).",
    )
    history_parser.add_argument(
        "--top",
        type=int,
        default=10,
        metavar="N",
        help="Number of largest historical blobs to report (default: 10).",
    )
    history_parser.add_argument(
        "--format",
        choices=["terminal", "markdown", "json"],
        default="terminal",
        help="Output report format (default: terminal).",
    )
    history_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        metavar="FILE",
        help="Save report to specified file path instead of stdout.",
    )
    history_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Overwrite existing output report file if it already exists.",
    )

    return parser


def handle_scan_command(args: argparse.Namespace) -> int:
    """Execute the 'scan' subcommand."""
    if args.top < 1:
        sys.stderr.write("Error: --top must be a positive integer greater than zero.\n")
        return 1

    repo_info = detect_repository(args.path)
    user_excludes = parse_exclude_argument(args.exclude)
    use_default = not args.no_default_excludes

    # 1. Working-tree scan
    scan_result = scan_working_tree(
        repo_info=repo_info,
        top_n=args.top,
        user_excludes=user_excludes,
        use_default_excludes=use_default,
    )

    # 2. .gitignore recommendations
    recommendations = check_gitignore_recommendations(repo_info)

    # 3. Optional history analysis
    history_analysis = None
    if args.include_history:
        history_analysis = analyze_git_history(repo_info, top_n=args.top)

    # Render format
    if args.format == "json":
        report_content = render_json_report(
            scan_result, recommendations, history_analysis
        )
    elif args.format == "markdown":
        report_content = render_markdown_report(
            scan_result, recommendations, history_analysis
        )
    elif args.format == "html":
        from gitsize.report import render_html_report
        report_content = render_html_report(
            scan_result, recommendations, history_analysis
        )
    else:
        report_content = render_terminal_report(
            scan_result, recommendations, history_analysis
        )

    # Handle output destination
    if args.output:
        try:
            saved_path = write_report_file(
                report_content, args.output, force=args.force
            )
            print(f"Report successfully written to: {saved_path}")
        except ReportExistsError as err:
            sys.stderr.write(f"Error: {err}\n")
            return 1
    else:
        print(report_content)

    return 0


def handle_web_command(args: argparse.Namespace) -> int:
    """Execute the 'web' subcommand: runs analysis and launches interactive web dashboard."""
    repo_info = detect_repository(args.path)
    scan_result = scan_working_tree(repo_info, top_n=20)
    recommendations = check_gitignore_recommendations(repo_info)
    history_analysis = analyze_git_history(repo_info, top_n=20)

    from gitsize.report import build_json_data, write_report_file
    from gitsize.web import generate_dashboard_html, start_local_dashboard_server

    data = build_json_data(scan_result, recommendations, history_analysis)
    html_content = generate_dashboard_html(data)

    # Save standalone report.html in workspace for offline viewing
    output_path = repo_info.root_path / "report.html"
    write_report_file(html_content, output_path, force=True)

    print("=" * 72)
    print(f"  GitSize v{__version__} - Interactive Web Dashboard")
    print("=" * 72)
    print(f"Standalone HTML report saved : {output_path}")

    try:
        server, url = start_local_dashboard_server(
            data, port=args.port, open_browser=not args.no_browse
        )
        print(f"Interactive Web Dashboard URL: {url}")
        print("Press Ctrl+C to terminate the local server.\n")
        # Keep serving until interrupted
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb dashboard server stopped.")
    except Exception as err:
        print(f"Local server notification: {err}")

    return 0


def handle_ignore_check_command(args: argparse.Namespace) -> int:
    """Execute the 'ignore-check' subcommand."""
    repo_info = detect_repository(args.path)
    recommendations = check_gitignore_recommendations(repo_info)

    if args.format == "json":
        output_dict = {
            "tool": "gitsize",
            "version": __version__,
            "repository": {
                "root_path": str(repo_info.root_path),
                "branch": repo_info.current_branch,
            },
            "recommendations": [
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
            ],
        }
        report_content = json.dumps(output_dict, indent=2)

    elif args.format == "markdown":
        lines = [
            f"# GitSize .gitignore Recommendation Report",
            "",
            f"Repository: `{repo_info.root_path}` | Branch: `{repo_info.current_branch or 'N/A'}`",
            "",
        ]
        if recommendations:
            lines.append("| Suggested Rule | Category | Detected Path | Unignored Size | Reason |")
            lines.append("| :--- | :--- | :--- | :---: | :--- |")
            for rec in recommendations:
                lines.append(
                    f"| `{rec.suggested_pattern}` | {rec.category} | `{rec.detected_path}` | {rec.formatted_size} | {rec.reason} |"
                )
            lines.append("")
            lines.append("> **Notice**: Suggestions are recommendations only. Verify requirements before updating .gitignore.")
        else:
            lines.append("No common missing .gitignore rules detected.")
        report_content = "\n".join(lines)

    else:
        lines = [
            "=" * 72,
            f"  GitSize v{__version__} - .gitignore Audit",
            "=" * 72,
            f"Repository Root : {repo_info.root_path}",
            f"Current Branch  : {repo_info.current_branch or 'N/A'}",
            "",
        ]
        if recommendations:
            headers = ["Suggested Rule", "Category", "Detected Path", "Size"]
            rows = [
                [r.suggested_pattern, r.category, r.detected_path, r.formatted_size]
                for r in recommendations
            ]
            lines.append(format_table(headers, rows, alignments=["<", "<", "<", ">"]))
            lines.append("")
            for r in recommendations:
                lines.append(f"* [{r.suggested_pattern}]: {r.reason}")
            lines.append("")
            lines.append("Review recommendations before manually appending to .gitignore.")
        else:
            lines.append("No common missing .gitignore patterns detected. Repository is clean!")
        lines.append("=" * 72)
        report_content = "\n".join(lines)

    if args.output:
        try:
            saved_path = write_report_file(
                report_content, args.output, force=args.force
            )
            print(f"Report successfully written to: {saved_path}")
        except ReportExistsError as err:
            sys.stderr.write(f"Error: {err}\n")
            return 1
    else:
        print(report_content)

    return 0


def handle_history_command(args: argparse.Namespace) -> int:
    """Execute the 'history' subcommand."""
    if args.top < 1:
        sys.stderr.write("Error: --top must be a positive integer greater than zero.\n")
        return 1

    repo_info = detect_repository(args.path)
    history_analysis = analyze_git_history(repo_info, top_n=args.top)

    if args.format == "json":
        output_dict = {
            "tool": "gitsize",
            "version": __version__,
            "repository": {
                "root_path": str(repo_info.root_path),
                "branch": repo_info.current_branch,
            },
            "history": {
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
            },
        }
        report_content = json.dumps(output_dict, indent=2)

    elif args.format == "markdown":
        lines = [
            f"# GitSize Historical Object Storage Report",
            "",
            f"Repository: `{repo_info.root_path}` | Branch: `{repo_info.current_branch or 'N/A'}`",
            "",
            "## Storage Context",
            "",
        ]
        for note in history_analysis.notes:
            lines.append(f"- {note}")
        lines.append("")
        lines.append(f"## Top {len(history_analysis.top_blobs)} Largest Historical Blobs")
        lines.append("")
        if history_analysis.top_blobs:
            lines.append("| Blob SHA | Historical Path | Object Size | Commit Reference | Working Tree Status |")
            lines.append("| :---: | :--- | :---: | :--- | :---: |")
            for b in history_analysis.top_blobs:
                status = "Deleted" if b.is_deleted_in_working_tree else "Active"
                lines.append(
                    f"| `{b.short_hash}` | `{b.path}` | {b.formatted_size} | {b.commit_ref or 'N/A'} | {status} |"
                )
        else:
            lines.append("_No historical Git blobs found._")
        report_content = "\n".join(lines)

    else:
        lines = [
            "=" * 72,
            f"  GitSize v{__version__} - Historical Storage Analysis",
            "=" * 72,
            f"Repository Root : {repo_info.root_path}",
            f"Current Branch  : {repo_info.current_branch or 'N/A'}",
            "",
            "Context Notes:",
        ]
        for note in history_analysis.notes:
            lines.append(f"  * {note}")
        lines.append("")
        lines.append(f"--- Top {len(history_analysis.top_blobs)} Largest Historical Blobs ---")
        if history_analysis.top_blobs:
            headers = ["Blob SHA", "Historical Path", "Size", "Commit Ref", "Status"]
            rows = [
                [
                    b.short_hash,
                    b.path,
                    b.formatted_size,
                    b.commit_ref or "(unknown)",
                    "Deleted in WT" if b.is_deleted_in_working_tree else "Active in WT",
                ]
                for b in history_analysis.top_blobs
            ]
            lines.append(format_table(headers, rows, alignments=["<", "<", ">", "<", "<"]))
        else:
            lines.append("No historical blobs found.")
        lines.append("=" * 72)
        report_content = "\n".join(lines)

    if args.output:
        try:
            saved_path = write_report_file(
                report_content, args.output, force=args.force
            )
            print(f"Report successfully written to: {saved_path}")
        except ReportExistsError as err:
            sys.stderr.write(f"Error: {err}\n")
            return 1
    else:
        print(report_content)

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Main CLI entry point for GitSize."""
    parser = create_parser()

    if argv is None:
        argv = sys.argv[1:]

    # If no arguments provided, show help
    if not argv:
        parser.print_help()
        return 0

    args = parser.parse_args(argv)

    try:
        if args.command == "scan":
            return handle_scan_command(args)
        elif args.command == "web":
            return handle_web_command(args)
        elif args.command == "ignore-check":
            return handle_ignore_check_command(args)
        elif args.command == "history":
            return handle_history_command(args)
        else:
            parser.print_help()
            return 0

    except (GitNotFoundError, NotAGitRepositoryError) as err:
        sys.stderr.write(f"Repository Error: {err}\n")
        return 2
    except ReportExistsError as err:
        sys.stderr.write(f"Error: {err}\n")
        return 1
    except (GitSizeError, ScanError) as err:
        sys.stderr.write(f"Execution Error: {err}\n")
        return 2
    except KeyboardInterrupt:
        sys.stderr.write("\nOperation aborted by user.\n")
        return 1
    except Exception as err:
        sys.stderr.write(f"Unexpected Error: {err}\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())

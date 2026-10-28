"""Tests for the command-line interface, subcommands, and exit codes."""

from pathlib import Path
import subprocess
import pytest

from gitsize.cli import main, parse_exclude_argument


@pytest.fixture
def test_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "cli_test_repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)

    (repo / "file1.py").write_text("print('hello')", encoding="utf-8")
    (repo / "data.bin").write_bytes(b"\x00" * 1024)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, check=True)
    return repo


def test_parse_exclude_argument():
    assert parse_exclude_argument("node_modules,.venv,dist") == ["node_modules", ".venv", "dist"]
    assert parse_exclude_argument("  node_modules ; .venv , build  ") == ["node_modules", ".venv", "build"]
    assert parse_exclude_argument(None) == []
    assert parse_exclude_argument("") == []


def test_cli_help(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "GitSize" in captured.out
    assert "scan" in captured.out
    assert "ignore-check" in captured.out
    assert "history" in captured.out


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0


def test_cli_no_args_shows_help(capsys):
    exit_code = main([])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "usage:" in captured.out


def test_cli_scan_default(test_repo: Path, capsys):
    exit_code = main(["scan", str(test_repo)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "GitSize" in captured.out
    assert "Top 2 Largest Files" in captured.out or "Top" in captured.out
    assert "file1.py" in captured.out


def test_cli_scan_json_output(test_repo: Path, capsys):
    exit_code = main(["scan", str(test_repo), "--format", "json"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert '"tool": "gitsize"' in captured.out
    assert '"working_tree"' in captured.out


def test_cli_scan_markdown_output(test_repo: Path, capsys):
    exit_code = main(["scan", str(test_repo), "--format", "markdown"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "# GitSize Repository Storage Analysis Report" in captured.out
    assert "## 1. Repository Information" in captured.out


def test_cli_scan_file_output_and_force(test_repo: Path, tmp_path: Path):
    output_file = tmp_path / "out_report.md"
    # First save succeeds
    exit_code = main(["scan", str(test_repo), "--format", "markdown", "--output", str(output_file)])
    assert exit_code == 0
    assert output_file.exists()

    # Second save without force fails with exit code 1
    exit_code_dup = main(["scan", str(test_repo), "--format", "markdown", "--output", str(output_file)])
    assert exit_code_dup == 1

    # Save with --force succeeds
    exit_code_force = main(["scan", str(test_repo), "--format", "markdown", "--output", str(output_file), "--force"])
    assert exit_code_force == 0


def test_cli_scan_invalid_top_argument(test_repo: Path, capsys):
    exit_code = main(["scan", str(test_repo), "--top", "0"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Error: --top must be a positive integer" in captured.err


def test_cli_scan_not_a_git_repo(tmp_path: Path, capsys):
    plain_dir = tmp_path / "not_git"
    plain_dir.mkdir()
    exit_code = main(["scan", str(plain_dir)])
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "Repository Error:" in captured.err


def test_cli_ignore_check(test_repo: Path, capsys):
    # Add an unignored .env file
    (test_repo / ".env").write_text("SECRET=123", encoding="utf-8")
    exit_code = main(["ignore-check", str(test_repo)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert ".env" in captured.out


def test_cli_ignore_check_json(test_repo: Path, capsys):
    exit_code = main(["ignore-check", str(test_repo), "--format", "json"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert '"recommendations"' in captured.out


def test_cli_history(test_repo: Path, capsys):
    exit_code = main(["history", str(test_repo), "--top", "5"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Historical Storage Analysis" in captured.out
    assert "file1.py" in captured.out or "data.bin" in captured.out


def test_cli_history_json(test_repo: Path, capsys):
    exit_code = main(["history", str(test_repo), "--format", "json"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert '"history"' in captured.out

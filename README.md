# GitSize — Git Repository Storage Analyzer

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests: Pytest](https://img.shields.io/badge/tests-pytest-purple.svg)](tests/)

**GitSize** is a lightweight, zero-dependency, read-only command-line developer tool written in Python. It analyzes Git repositories to identify oversized working-tree files, historical commit bloat, file-type storage distributions, and common `.gitignore` omissions before they pollute remote repositories.

---

## 1. Project Overview & Motivation

As software projects evolve, repositories unintentionally accumulate excessive storage overhead:
- Unignored local virtual environments (`.venv/`) and package caches (`node_modules/`, `__pycache__/`) get tracked.
- Test datasets, build artifacts (`dist/`), and secret files (`.env`) get committed accidentally.
- Files deleted in recent commits **remain permanently in Git history**, continuing to bloat `git clone` download times and server storage.

Existing solutions often require heavy package installations, complex bash scripts, or dangerous garbage-collection commands. **GitSize** solves this with a clean, safe, and portable CLI tool that strictly uses the Python standard library and native Git CLI commands.

---

## 2. Resume & Portfolio Bullet Points

> **GitSize — Git Repository Storage Analyzer (Python, Git CLI, Pytest)**
> - Engineered an open-source, read-only CLI storage analyzer in Python 3.11+ using `argparse`, `pathlib`, and `subprocess` to audit repository disk usage and Git object databases.
> - Implemented an intelligent `.gitignore` recommendation engine that audits working trees against standard ignore patterns and active Git ignore rules without exposing secret file contents.
> - Built a Git history inspection engine using `rev-list` and `cat-file` to detect and deduplicate oversized historical blobs, distinguishing active working-tree files from permanent history bloat.
> - Formatted multi-format reporting (aligned ASCII terminal tables, GitHub Flavored Markdown, and structured JSON) with fail-safe file writing guards.
> - Authored an automated suite of 50+ unit and integration tests with `pytest` utilizing isolated temporary Git repositories, achieving comprehensive coverage across Windows and Unix platforms.

---

## 3. Core Features & Guarantees

| Feature | Description |
| :--- | :--- |
| **Repository Detection** | Accurately identifies Git root from any subdirectory; handles detached HEAD states, shallow clones, and unborn branch states. |
| **Working-Tree Scanner** | Discovers tracked and untracked files; calculates exact bytes and human-readable units; computes top-N files and file-type breakdowns. |
| **Configurable Exclusions** | Automatically filters `.git/`, `.venv/`, `node_modules/`, `dist/`, etc., while supporting custom comma-separated exclusion patterns. |
| **.gitignore Diagnostic** | Scans for unignored build directories, virtual environments, editor caches, and credentials; recommends non-destructive fixes. |
| **Git History Analysis** | Inspects the `.git` object database; deduplicates identical blob SHAs; identifies files that were deleted from disk but remain in history. |
| **Multi-Format Reports** | Outputs clean aligned terminal tables, GitHub-ready Markdown reports, or machine-readable JSON schemas. |
| **Read-Only Safety** | **Strictly read-only.** Never deletes files, never modifies `.gitignore`, never rewrites history, and never executes destructive commands. |
| **Security First** | Never reads or prints the contents of sensitive files (such as `.env` credentials). |

---

## 4. Prerequisites

- **Python**: Version 3.11 or newer (tested on Python 3.11, 3.12, 3.13, 3.14).
- **Git**: Git 2.20+ installed and available on system PATH (`git --version`).
- **Operating System**: Windows 11 / 10, macOS, or Linux.

---

## 5. Windows 11 PowerShell Installation & Setup

### A. Clone and Setup Virtual Environment

Open PowerShell in your workspace directory:

```powershell
# 1. Create a clean virtual environment
py -3 -m venv .venv

# 2. Activate the virtual environment
.\.venv\Scripts\Activate.ps1
```

> **PowerShell Execution Policy Alternative:**
> If PowerShell blocks `Activate.ps1` with an execution policy error (`PSSecurityException`), run either:
>
> ```powershell
> # Option 1: Temporarily allow script execution in current PowerShell window (non-admin)
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> .\.venv\Scripts\Activate.ps1
> ```
>
> Or invoke the virtual environment's Python executable directly without activation:
> ```powershell
> # Option 2: Direct executable invocation
> .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
> ```

### B. Install in Editable Mode

Install GitSize and test dependencies (`pytest`):

```powershell
python -m pip install -e ".[dev]"
```

### C. Verify CLI Installation

```powershell
gitsize --version
gitsize --help
```

---

## 6. Usage & CLI Commands

### 1. Working-Tree Storage Scan

Scan the current repository working tree (defaults to top 10 files and built-in exclusions):

```powershell
gitsize scan .
```

Scan with custom options (e.g. top 20 files, excluding custom directories):

```powershell
gitsize scan . --top 20 --exclude "temp,logs,coverage"
```

Include Git historical blob analysis directly in the scan:

```powershell
gitsize scan . --include-history
```

### 2. .gitignore Hygiene Check

Audit repository for unignored development artifacts (e.g. `.venv`, `__pycache__`, `.env`, `node_modules`):

```powershell
gitsize ignore-check .
```

### 3. Historical Git Object Analysis

Inspect historical Git blob objects, discovering large files that were committed in the past (even if subsequently deleted):

```powershell
gitsize history . --top 10
```

### 4. Interactive Web Dashboard

Launch the zero-dependency, local web dashboard in your browser with interactive file search, distribution graphs, and dark/light themes:

```powershell
# Start local dashboard and open in default web browser
gitsize web .

# Launch on a custom port
gitsize web . --port 8080

# Generate standalone offline HTML report without starting a server
gitsize scan . --format html --output report.html
```

### 5. Exporting Reports (Markdown, JSON & HTML)

Export structured reports to disk. By default, GitSize refuses to overwrite existing files to prevent accidental data loss:

```powershell
# Export GitHub Flavored Markdown report
gitsize scan . --format markdown --output report.md

# Export structured JSON report
gitsize scan . --format json --output report.json

# Export standalone interactive HTML report
gitsize scan . --format html --output report.html

# Overwrite existing report file using --force (-f)
gitsize scan . --format markdown --output report.md --force
```

---

## 7. Example Terminal Output

### Running `gitsize scan .`

```text
========================================================================
  GitSize v0.1.0 - Repository Storage Analysis
========================================================================
Repository Root    : C:\Users\speedy\Desktop\DAY4
Current Branch     : main
Working Tree Size  : 105.91 KB (25 files scanned)
Git Metadata (.git): 580.66 KB (local repository database)
Exclusions Applied : .git, node_modules, .venv, venv, dist, build, __pycache__, .pytest_cache, .mypy_cache, .ruff_cache

--- Top 10 Largest Files (Working Tree) ---
Rank  Path                               Size     Bytes
----  -----------------------------  --------  --------
#1    src/gitsize/cli.py             16.35 KB  16,743 B
#2    src/gitsize/report.py          15.54 KB  15,917 B
#3    src/gitsize/scanner.py         10.99 KB  11,255 B
#4    src/gitsize/ignore_checker.py  10.18 KB  10,427 B
#5    src/gitsize/history.py          6.89 KB   7,055 B
#6    src/gitsize/repository.py       6.81 KB   6,977 B
#7    tests/test_scanner.py           6.54 KB   6,697 B
#8    tests/test_report.py            5.51 KB   5,645 B
#9    tests/test_ignore_checker.py    5.19 KB   5,315 B
#10   tests/test_cli.py               4.88 KB   5,000 B

--- Storage by File Type ---
Extension       Count  Total Size  % Total
--------------  -----  ----------  -------
.py                16   101.62 KB    95.9%
(no extension)      2     2.13 KB     2.0%
.toml               1     1.28 KB     1.2%
.txt                5       526 B     0.5%
.gitignore          1       383 B     0.3%

--- .gitignore Recommendations ---
No common missing .gitignore patterns detected. Working tree looks clean!

========================================================================
```

### Running `gitsize history . --top 5`

```text
========================================================================
  GitSize v0.1.0 - Historical Storage Analysis
========================================================================
Repository Root : C:\Users\speedy\Desktop\DAY4
Current Branch  : main

Context Notes:
  * Historical sizes reflect uncompressed Git blob object sizes, not compressed packfile disk usage.
  * Deleted files still remain in Git history and contribute to repository clone download sizes.

--- Top 5 Largest Historical Blobs ---
Blob SHA  Historical Path                 Size  Commit Ref              Status       
--------  --------------------------  --------  ----------------------  -------------
8b44943d  frontend/package-lock.json  53.10 KB  3d2c605 Initial commit  Deleted in WT
ab022992  frontend/package-lock.json  51.08 KB  3d2c605 Initial commit  Deleted in WT
ac9f5c67  backend/nodes/registry.py   40.77 KB  3d2c605 Initial commit  Deleted in WT
70476a2e  frontend/src/App.tsx        30.27 KB  3d2c605 Initial commit  Deleted in WT
69f2e398  app/static/css/styles.css   26.61 KB  de4d4ee Initial commit  Deleted in WT
========================================================================
```

See [`examples/sample_report.md`](examples/sample_report.md) for a complete Markdown export example.

---

## 8. How GitSize Handles Git History

Git stores historical data as immutable directed acyclic graph (DAG) objects. When a developer deletes a large file using `git rm` or `rm`, **the file is removed from the working tree but remains permanently embedded in historical Git commits**.

1. **Discovery**: GitSize executes `git rev-list --objects --all` to stream all commit, tree, and blob references across all branches and tags.
2. **Deduplication**: In Git, two identical files share the exact same SHA-1/SHA-256 blob identifier. GitSize groups historical entries by blob hash so identical copies are counted once.
3. **Bulk Sizing**: Blob hashes are batched into `git cat-file --batch-check` to read uncompressed object sizes without checking out files.
4. **Targeted Resolution**: Commit origins (`git log -1 --find-object`) and working-tree deletion statuses are resolved strictly for the top-N results to ensure optimal speed.
5. **No Destructive Operations**: GitSize **never** runs `git gc`, `git prune`, or `git filter-repo`. It is an inspection and advisory tool only.

---

## 9. Safety & Security Guarantees

- **100% Read-Only**: Never writes, modifies, renames, stages, or deletes repository files.
- **Subprocess Security**: Commands use strict argument lists with `subprocess.run(..., check=False)` with explicit timeouts. No shell command strings (`shell=True` is prohibited).
- **Symlink Protection**: Resolves symbolic links and actively checks repository boundaries. Symlinks pointing outside the repository root are recorded as warnings and never traversed.
- **Secrets Protection**: Environment files (`.env`, `.env.local`) are audited for presence and size only. File contents are **never read or displayed**.
- **Resilient Error Handling**: Safely catches `PermissionError`, missing files that vanish during scanning, and non-UTF-8 filenames without crashing.

---

## 10. Automated Testing

The automated test suite uses `pytest` and runs entirely within isolated temporary Git repositories (`tmp_path`). It does not interact with or depend on your real projects or private files.

Run all tests:

```powershell
pytest -q
```

### Test Coverage Highlights:
- **`test_repository.py`**: Valid repo detection, subdirectories, empty repositories (0 commits), detached HEAD, invalid paths, and missing Git binary handling.
- **`test_scanner.py`**: Top-N largest file sorting, file-type aggregation, directory exclusions, external symlink prevention, permission errors, and SHA-256 non-modification verification.
- **`test_ignore_checker.py`**: Missing rule detection, duplicate avoidance, already-ignored recognition (`git check-ignore`), and secret token leakage prevention.
- **`test_history.py`**: Historical blob deduplication, deleted file detection, empty repo handling, and top-N limits.
- **`test_report.py`**: Markdown section compliance, JSON schema validation, and overwrite protection.
- **`test_cli.py`**: All subcommands, arguments, formatters, and exit code contracts (0 = success, 1 = user error, 2 = operational/git error).

---

## 11. Known Limitations & Future Improvements

- **Packed Objects vs Working Tree**: Historical object sizes indicate uncompressed blob sizes. On disk, Git objects may be delta-compressed inside packfiles.
- **Git LFS Pointers**: Files tracked via Git Large File Storage (Git LFS) appear in the working tree as small pointer text files unless LFS smudge filters have fetched the full binary.
- **Future Improvements**:
  - Optional interactive TUI dashboard using Python's standard `curses` module.
  - Automated detection of historical Git LFS candidates.
  - Custom `.gitsizerc` configuration files for organizational ignore presets.

---

## 12. License

This project is licensed under the terms of the [MIT License](LICENSE).
# gitsize

"""Unit tests for formatting utilities."""

import pytest
from gitsize.formatting import format_bytes, format_table


def test_format_bytes_zero_and_small():
    assert format_bytes(0) == "0 B"
    assert format_bytes(512) == "512 B"
    assert format_bytes(1023) == "1023 B"


def test_format_bytes_kilobytes():
    assert format_bytes(1024) == "1.00 KB"
    assert format_bytes(1536) == "1.50 KB"
    assert format_bytes(2048) == "2.00 KB"


def test_format_bytes_megabytes_and_gigabytes():
    assert format_bytes(1024 * 1024) == "1.00 MB"
    assert format_bytes(1024 * 1024 * 1024) == "1.00 GB"
    assert format_bytes(2.5 * 1024 * 1024 * 1024) == "2.50 GB"


def test_format_bytes_negative():
    assert format_bytes(-1024) == "-1.00 KB"


def test_format_table_empty():
    assert format_table([], []) == ""


def test_format_table_alignment_and_padding():
    headers = ["Name", "Size", "Count"]
    rows = [
        ["app.py", "1.50 KB", "10"],
        ["main.rs", "32.00 KB", "120"],
    ]
    table = format_table(headers, rows, alignments=["<", ">", ">"])
    lines = table.splitlines()

    assert len(lines) == 4  # Header, divider, 2 rows
    assert "Name" in lines[0]
    assert "Size" in lines[0]
    assert "Count" in lines[0]
    assert "---" in lines[1]
    assert "app.py" in lines[2]
    assert "main.rs" in lines[3]

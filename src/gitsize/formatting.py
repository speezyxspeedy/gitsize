"""Formatting utilities for human-readable output, byte sizes, and terminal tables."""

from typing import Sequence


def format_bytes(size: int | float, decimal_places: int = 2) -> str:
    """Format a byte count into a human-readable string (B, KB, MB, GB, TB).

    Uses binary prefixes (1024 base).

    Args:
        size: Size in bytes (integer or float).
        decimal_places: Number of decimal places to format.

    Returns:
        Formatted string like "512 B", "4.25 KB", "12.80 MB", "1.50 GB".
    """
    if size < 0:
        return f"-{format_bytes(-size, decimal_places)}"
    if size == 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    value = float(size)
    unit_idx = 0

    while value >= 1024.0 and unit_idx < len(units) - 1:
        value /= 1024.0
        unit_idx += 1

    if unit_idx == 0:
        return f"{int(value)} B"
    return f"{value:.{decimal_places}f} {units[unit_idx]}"


def format_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    alignments: Sequence[str] | None = None,
) -> str:
    """Render a clean, aligned plain-text table without external dependencies.

    Args:
        headers: Column header names.
        rows: Rows of string values matching header count.
        alignments: Optional alignment characters ('<' for left, '>' for right, '^' for center)
                    per column. Defaults to left alignment.

    Returns:
        Rendered multi-line table string.
    """
    if not headers:
        return ""

    num_cols = len(headers)
    aligns = list(alignments) if alignments else ["<"] * num_cols
    while len(aligns) < num_cols:
        aligns.append("<")

    # Determine maximum width needed for each column
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx in range(min(num_cols, len(row))):
            col_widths[idx] = max(col_widths[idx], len(str(row[idx])))

    # Format header row
    header_cells = [
        f"{headers[i]:{aligns[i]}{col_widths[i]}}"
        for i in range(num_cols)
    ]
    header_line = "  ".join(header_cells)

    # Format divider
    divider_line = "  ".join("-" * col_widths[i] for i in range(num_cols))

    # Format data rows
    data_lines = []
    for row in rows:
        cells = []
        for i in range(num_cols):
            val = str(row[i]) if i < len(row) else ""
            cells.append(f"{val:{aligns[i]}{col_widths[i]}}")
        data_lines.append("  ".join(cells))

    lines = [header_line, divider_line]
    lines.extend(data_lines)
    return "\n".join(lines)

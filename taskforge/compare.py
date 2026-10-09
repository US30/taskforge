"""Compare an output folder with the expected one and describe the differences in words the model can act on."""
from __future__ import annotations

import csv
import json
from pathlib import Path

TOL = 0.011
MAX_NOTES = 4


def _same(a, b) -> bool:
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    try:  # numbers match within a paisa whether written as 7.5, "7.50" or 7.500
        return abs(float(a) - float(b)) <= TOL
    except (TypeError, ValueError):
        return str(a).strip() == str(b).strip()


def _csv_diff(got: Path, want: Path) -> list[str]:
    with open(got, newline="") as f, open(want, newline="") as g:
        a, b = list(csv.reader(f)), list(csv.reader(g))
    a, b = [r for r in a if r], [r for r in b if r]
    if not a or [c.strip() for c in a[0]] != b[0]:
        return [f"header is {a[0] if a else 'missing'}, expected {b[0]}"]
    notes = [f"has {len(a) - 1} data rows, expected {len(b) - 1}"] if len(a) != len(b) else []
    for i, (x, y) in enumerate(zip(a[1:], b[1:]), 1):
        if not _same(x, y):
            notes.append(f"row {i} is {x}, expected {y}")
    return notes


def _json_diff(got: Path, want: Path) -> list[str]:
    try:
        a = json.loads(got.read_text())
    except json.JSONDecodeError as e:
        return [f"is not valid JSON ({e.msg})"]
    b = json.loads(want.read_text())
    if _same(a, b):
        return []
    if isinstance(a, dict) and isinstance(b, dict):
        notes = [f"missing key {k!r}" for k in b.keys() - a.keys()] + [f"unexpected key {k!r}" for k in a.keys() - b.keys()]
        notes += [f"key {k!r} is {json.dumps(a[k])[:200]}, expected {json.dumps(b[k])[:200]}" for k in b.keys() & a.keys() if not _same(a[k], b[k])]
        return sorted(notes)
    return [f"content is {json.dumps(a)[:300]}, expected {json.dumps(b)[:300]}"]


def compare_dirs(got: Path, want: Path) -> list[str]:
    """Problems found, in plain words. Empty list means the output is correct."""
    have, need = {p.name for p in got.iterdir() if p.is_file()}, {p.name for p in want.iterdir() if p.is_file()}
    notes = [f"missing output file {n}" for n in sorted(need - have)] + [f"unexpected output file {n}" for n in sorted(have - need)]
    for n in sorted(have & need):
        diff = (_csv_diff if n.endswith(".csv") else _json_diff if n.endswith(".json") else
                lambda a, b: [] if a.read_text().strip() == b.read_text().strip() else ["text differs"])(got / n, want / n)
        notes += [f"{n}: {d}" for d in diff[:MAX_NOTES]] + ([f"{n}: ... and {len(diff) - MAX_NOTES} more differences"] if len(diff) > MAX_NOTES else [])
    return notes

"""Public path-fraction mismatch level m and sample-index kinematics.

This is the m described in Hartman, Kinetic Analysis of Informational Disorder,
v2.4 (2026), Section 5: baseline-only SHA-256 path fraction. It is not a
production estimator.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def digest_tree(root: Path, *, ignore_names: frozenset[str] = frozenset({".git"})) -> dict[str, str]:
    files: dict[str, str] = {}
    root = root.resolve()
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel_parts = path.relative_to(root).parts
        if any(part in ignore_names for part in rel_parts):
            continue
        rel = path.relative_to(root).as_posix()
        files[rel] = sha256_file(path)
    return files


def public_m(baseline: dict[str, str], live: dict[str, str]) -> float:
    n0 = len(baseline)
    if n0 == 0:
        raise ValueError("baseline is empty")
    k = 0
    for path, digest in baseline.items():
        if live.get(path) != digest:
            k += 1
    return k / n0


def public_m_bin(baseline: dict[str, str], live: dict[str, str]) -> int:
    """Binary m: 0 if every baseline path matches, else 1."""
    for path, digest in baseline.items():
        if live.get(path) != digest:
            return 1
    return 0


def kinematics(history: list[float]) -> tuple[float | None, float | None]:
    n = len(history)
    if n < 2:
        return None, None
    delta = history[-1] - history[-2]
    a = None
    if n >= 3:
        prev_delta = history[-2] - history[-3]
        a = delta - prev_delta
    return delta, a

"""Synthetic family A for public path-fraction m. No product logs."""

from __future__ import annotations

from pathlib import Path

import pytest

from public_m import kinematics, public_m


def _sha_payload(i: int) -> bytes:
    return bytes([i % 256]) * 8


def _write_tree(root: Path, n: int) -> dict[str, str]:
    from public_m import sha256_file

    files: dict[str, str] = {}
    for i in range(n):
        rel = f"f{i:03d}.bin"
        dest = root / rel
        dest.write_bytes(_sha_payload(i))
        files[rel] = sha256_file(dest)
    return files


def _flip(root: Path, rel: str) -> str:
    from public_m import sha256_file

    path = root / rel
    path.write_bytes(path.read_bytes() + b"x")
    return sha256_file(path)


def test_a_undefined_until_three_samples():
    assert kinematics([]) == (None, None)
    assert kinematics([0.1]) == (None, None)
    delta, a = kinematics([0.1, 0.2])
    assert delta == 0.1
    assert a is None
    delta, a = kinematics([0.1, 0.2, 0.4])
    assert delta == 0.2
    assert a == 0.1


def test_a_stable_acceleration_near_zero(tmp_path: Path):
    root = tmp_path / "t"
    root.mkdir()
    live = _write_tree(root, 100)
    baseline = dict(live)
    series = [public_m(baseline, live)]
    for rel in list(live)[:10]:
        live[rel] = _flip(root, rel)
    series.append(public_m(baseline, live))
    series.append(public_m(baseline, live))
    series.append(public_m(baseline, live))
    assert series[-1] == 0.10
    _delta, a = kinematics(series)
    assert a is not None
    assert abs(a) < 1e-12


def test_a_steady_linear_leak_acceleration_near_zero(tmp_path: Path):
    root = tmp_path / "t"
    root.mkdir()
    live = _write_tree(root, 100)
    baseline = dict(live)
    names = list(live)
    history = [public_m(baseline, live)]
    cursor = 0
    last_a = None
    last_delta = None
    for _ in range(4):
        for rel in names[cursor : cursor + 2]:
            live[rel] = _flip(root, rel)
        cursor += 2
        history.append(public_m(baseline, live))
        last_delta, last_a = kinematics(history)
    assert last_delta == pytest.approx(0.02)
    assert last_a is not None
    assert abs(last_a) < 1e-12


def test_a_accel_positive_before_m_saturates(tmp_path: Path):
    root = tmp_path / "t"
    root.mkdir()
    live = _write_tree(root, 50)
    baseline = dict(live)
    names = list(live)
    history = [public_m(baseline, live)]
    cursor = 0
    chunk = 1
    seen = False
    while cursor < 50:
        take = min(chunk, 50 - cursor)
        for rel in names[cursor : cursor + take]:
            live[rel] = _flip(root, rel)
        cursor += take
        chunk *= 2
        history.append(public_m(baseline, live))
        m = history[-1]
        _delta, a = kinematics(history)
        if a is not None and m < 1.0 and a > 0:
            seen = True
            break
    assert seen

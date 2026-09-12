"""Observational family B: git archive, public m, CSVs, tables.

Frozen windows and split are in CORPUS.md. Rules are in METHODS.md.
Do not change sampling, m, or labels after inspecting revert counts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import random
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from public_m import (
    kinematics,
    m_from_log,
    path_status,
    public_m,
    public_m_bin,
    sha256_file,
)

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "corpus-work"
RESULTS_V1 = ROOT / "results"
RESULTS_V2 = ROOT / "results-v2"
RESULTS_V3 = ROOT / "results-v3"
RESULTS_V3C = ROOT / "results-v3c"
RESULTS_A = ROOT / "results-a"
K = 25
BOOT_SEED = 20260908
BOOT_B = 10000
Z_WILSON = 1.959963984540054
LEAD_W = (5, 10)
ROLL_EVERY = 20
MAX_FIRST_PARENT = 2000
REVERT_SUBJ = re.compile(r"(?i)^revert\b")
REVERT_BODY = re.compile(r"(?i)\bthis reverts\b")

WINDOWS_V1 = [
    {
        "id": "f1",
        "name": "pallets/flask",
        "remote": "https://github.com/pallets/flask.git",
        "start": "2f0c62f5e6e290843f03c1fa70817c7a3c7fd661",
        "end": "735a4701d6d5e848241e7d7535db898efb62d400",
        "split": "train",
        "clone_name": "flask",
    },
    {
        "id": "h1",
        "name": "httpie/cli",
        "remote": "https://github.com/httpie/cli.git",
        "start": "88140422a9d6585a7edfb2c265ebed5d0736df2c",
        "end": "2105caa49bae87c5809c274e407619a0de2639d1",
        "split": "test",
        "clone_name": "httpie-cli",
    },
]

WINDOWS_V2 = [
    {
        "id": "d1",
        "name": "django/django",
        "remote": "https://github.com/django/django.git",
        "start": "174d8157b5700f6451ac0bdc3eef7e73121bc4a4",
        "end": "d88ec42bd0a37340c8477a6f20bf26e58bd84735",
        "split": "train",
        "clone_name": "django",
    },
    {
        "id": "c1",
        "name": "python/cpython",
        "remote": "https://github.com/python/cpython.git",
        "start": "1f6c87ca7b9351b2e5c5363504796fce0554c9b8",
        "end": "2849cbb53afc8c6a4465f1b3490c67c2455caf6f",
        "split": "test",
        "clone_name": "cpython",
    },
]

WINDOWS = WINDOWS_V1
RESULTS = RESULTS_V1

SERIES_FIELDS = [
    "sample",
    "first_parent_index",
    "sha",
    "n0",
    "m",
    "delta_m",
    "a",
    "m_bin",
    "delta_m_bin",
    "a_bin",
    "m_from_log",
    "revert_commit",
    "event_sample",
]

SERIES_FIELDS_ROLL = SERIES_FIELDS + [
    "roll_baseline_sample",
    "n0_roll",
    "m_roll",
    "delta_m_roll",
    "a_roll",
    "m_from_log_roll",
]

T1_FIELDS = [
    "window",
    "repo",
    "split",
    "w",
    "n_positive",
    "n_negative",
    "positives_lead_rise",
    "negatives_lead_rise",
    "positives_lead_rise_m_lt_0.5",
]

T1_MATCH_FIELDS = T1_FIELDS + [
    "n_events",
    "n_dropped_short",
    "n_dropped_contaminated",
    "n_dropped_no_a",
    "n_matched",
]

WALL_FIELDS = [
    "window",
    "repo",
    "sample",
    "sha",
    "committer_unix",
    "committer_iso",
    "hours_since_prev_sample",
    "flag_unix_lt_1",
    "flag_before_first_parent",
]


def run_git(repo: Path | None, args: list[str], *, cwd: Path | None = None) -> str:
    cmd = ["git"]
    if repo is not None:
        cmd.extend(["-C", str(repo)])
    cmd.extend(args)
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {err}")
    return proc.stdout


def ensure_clone(window: dict) -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    dest = WORK / window["clone_name"]
    if not (dest / ".git").is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        print(f"clone {window['remote']}", flush=True)
        run_git(None, ["clone", "--quiet", window["remote"], str(dest)])
    else:
        print(f"fetch {window['name']}", flush=True)
        run_git(dest, ["fetch", "--quiet", "origin"])
    return dest


def first_parent_shas(repo: Path, start: str, end: str) -> list[str]:
    anc = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", start, end],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if anc.returncode != 0:
        raise RuntimeError(f"{start} is not an ancestor of {end} in {repo}")
    mid = run_git(repo, ["rev-list", "--first-parent", "--reverse", f"{start}..{end}"])
    rest = [line.strip() for line in mid.splitlines() if line.strip()]
    start_full = run_git(repo, ["rev-parse", start]).strip()
    end_full = run_git(repo, ["rev-parse", end]).strip()
    shas = [start_full] + rest
    if shas[-1] != end_full:
        shas.append(end_full)
    out: list[str] = []
    seen: set[str] = set()
    for sha in shas:
        if sha not in seen:
            seen.add(sha)
            out.append(sha)
    return out


def is_revert_message(subject: str, body: str) -> bool:
    if REVERT_SUBJ.search(subject.strip()):
        return True
    if REVERT_BODY.search(subject) or REVERT_BODY.search(body):
        return True
    return False


def commit_message(repo: Path, sha: str) -> tuple[str, str]:
    raw = run_git(repo, ["log", "-1", "--format=%s%n%b", sha])
    subject, _, body = raw.partition("\n")
    return subject.strip(), body


def sample_indices(n: int, k: int) -> list[int]:
    if n <= 0:
        return []
    idx = list(range(0, n, k))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    return idx


ARCHIVE_PATH_BATCH = 40


def digest_git_tar(data: bytes) -> dict[str, str]:
    files: dict[str, str] = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            name = member.name.replace("\\", "/")
            if name.startswith("./"):
                name = name[2:]
            if any(part == ".git" for part in name.split("/")):
                continue
            src = tf.extractfile(member)
            if src is None:
                continue
            h = hashlib.sha256()
            while True:
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
            files[name] = h.hexdigest()
    return files


def git_archive_bytes(repo: Path, sha: str, paths: list[str] | None = None) -> bytes:
    cmd = ["git", "-C", str(repo), "archive", "--format=tar", sha]
    if paths:
        cmd.append("--")
        cmd.extend(paths)
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"git archive {sha[:12]} failed: {err}")
    return proc.stdout


def archive_tree(
    repo: Path,
    sha: str,
    *,
    prev_sha: str | None = None,
    prev_map: dict[str, str] | None = None,
) -> dict[str, str]:
    if prev_sha and prev_map:
        live = dict(prev_map)
        raw = run_git(
            repo,
            ["diff-tree", "-r", "--no-renames", "--name-status", prev_sha, sha],
        )
        to_hash: list[str] = []
        for line in raw.splitlines():
            line = line.strip("\n")
            if not line or "\t" not in line:
                continue
            status, path = line.split("\t", 1)
            kind = status[:1]
            if kind == "D":
                live.pop(path, None)
            elif kind in "AMTC":
                to_hash.append(path)
        hashed: dict[str, str] = {}
        for i in range(0, len(to_hash), ARCHIVE_PATH_BATCH):
            batch = to_hash[i : i + ARCHIVE_PATH_BATCH]
            hashed.update(digest_git_tar(git_archive_bytes(repo, sha, batch)))
        for path in to_hash:
            if path in hashed:
                live[path] = hashed[path]
            else:
                live.pop(path, None)
        return live
    return digest_git_tar(git_archive_bytes(repo, sha))


def revert_shas_for_walk(repo: Path, all_shas: list[str]) -> set[str]:
    if not all_shas:
        return set()
    start, end = all_shas[0], all_shas[-1]
    raw = run_git(
        repo,
        ["log", "--first-parent", "--format=%H%x00%s%x00%b%x1e", f"{start}^..{end}"],
    )
    wanted = set(all_shas)
    found: set[str] = set()
    for rec in raw.split("\x1e"):
        rec = rec.strip("\n")
        if not rec:
            continue
        sha, _, rest = rec.partition("\0")
        subj, _, body = rest.partition("\0")
        if sha in wanted and is_revert_message(subj, body):
            found.add(sha)
    return found


def lead_max_abs(dm_series: list[float | None], e: int, w: int) -> float | None:
    start = e - w
    if start < 0:
        return None
    vals = [abs(dm_series[j]) for j in range(start, e) if dm_series[j] is not None]
    if not vals:
        return None
    return max(vals)


def lead_max_a(a_series: list[float | None], e: int, w: int) -> float | None:
    start = e - w
    if start < 0 or e < 1:
        return None
    vals = [a_series[j] for j in range(start, e) if a_series[j] is not None]
    if not vals:
        return None
    return max(vals)


def lead_m_ok(m_series: list[float], e: int, w: int, cap: float) -> bool:
    start = e - w
    if start < 0:
        return False
    return all(m_series[j] < cap for j in range(start, e))


def youden_tau(scores: list[float], labels: list[int]) -> tuple[float | None, dict]:
    if not scores or not any(labels) or not any(1 - x for x in labels):
        return None, {"n": len(scores), "positives": sum(labels), "note": "Youden undefined (need both classes)"}
    order = sorted(set(scores), reverse=True)
    best_j = -1.0
    best_tau = order[0]
    n_pos = sum(labels)
    n_neg = len(labels) - n_pos
    for tau in order:
        tp = sum(1 for s, y in zip(scores, labels) if s >= tau and y == 1)
        fp = sum(1 for s, y in zip(scores, labels) if s >= tau and y == 0)
        tpr = tp / n_pos
        fpr = fp / n_neg
        j = tpr - fpr
        if j > best_j:
            best_j = j
            best_tau = tau
    return best_tau, {
        "n": len(scores),
        "positives": n_pos,
        "negatives": n_neg,
        "youden_j": best_j,
        "tau": best_tau,
    }


def class_metrics(scores: list[float], labels: list[int], tau: float) -> dict:
    pred = [1 if s >= tau else 0 for s in scores]
    tp = sum(1 for p, y in zip(pred, labels) if p == 1 and y == 1)
    fp = sum(1 for p, y in zip(pred, labels) if p == 1 and y == 0)
    tn = sum(1 for p, y in zip(pred, labels) if p == 0 and y == 0)
    fn = sum(1 for p, y in zip(pred, labels) if p == 0 and y == 1)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    return {
        "precision": prec,
        "recall": rec,
        "false_positive_rate": fpr,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
    }


def event_sample_indices(all_shas: list[str], sampled: list[int], revert_shas: set[str]) -> list[int]:
    sampled_shas = [all_shas[i] for i in sampled]
    events: list[int] = []
    for i, sha in enumerate(all_shas):
        if sha not in revert_shas:
            continue
        e = None
        for s_idx, s_sha in zip(range(len(sampled_shas)), sampled_shas):
            # first sampled commit at or after this revert in first-parent order
            if all_shas.index(s_sha) >= i:
                e = s_idx
                break
        if e is not None and e not in events:
            events.append(e)
    return events


def classify_points(
    m_series: list[float],
    a_series: list[float | None],
    events: set[int],
    w: int,
) -> tuple[list[dict], list[dict]]:
    n = len(m_series)
    positives: list[dict] = []
    negatives: list[dict] = []
    for e in range(w, n):
        mx = lead_max_a(a_series, e, w)
        if mx is None:
            continue
        row = {
            "e": e,
            "max_a": mx,
            "m_lt_1": lead_m_ok(m_series, e, w, 1.0),
            "m_lt_0_5": lead_m_ok(m_series, e, w, 0.5),
            "rise": mx > 0 and lead_m_ok(m_series, e, w, 1.0),
            "rise_strict": mx > 0 and lead_m_ok(m_series, e, w, 0.5),
        }
        if e in events:
            positives.append(row)
        else:
            negatives.append(row)
    return positives, negatives


def committer_meta(repo: Path, sha: str) -> tuple[int, str]:
    raw = run_git(repo, ["log", "-1", "--format=%ct%n%cI", sha])
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    unix = int(lines[0])
    iso = lines[1] if len(lines) > 1 else ""
    return unix, iso


def first_parent_committer_unix(repo: Path, sha: str) -> int | None:
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", f"{sha}^"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        return None
    parent = proc.stdout.strip()
    return int(run_git(repo, ["log", "-1", "--format=%ct", parent]).strip())


def control_first_parent_range_contaminated(
    sampled: list[int],
    all_shas: list[str],
    revert_shas: set[str],
    e: int,
    w: int,
) -> bool:
    i0 = sampled[e - 2 * w]
    i1 = sampled[e - w]
    for i in range(i0, i1):
        if all_shas[i] in revert_shas:
            return True
    return False


def matched_pair_rows(
    a_series: list[float | None],
    m_series: list[float],
    dm_series: list[float | None],
    events: set[int],
    sampled: list[int],
    all_shas: list[str],
    revert_shas: set[str],
    w: int,
) -> tuple[list[dict], dict]:
    stats = {
        "n_events": len(events),
        "n_dropped_short": 0,
        "n_dropped_contaminated": 0,
        "n_dropped_no_a": 0,
        "n_matched": 0,
    }
    pairs: list[dict] = []
    for e in sorted(events):
        if e < 2 * w:
            stats["n_dropped_short"] += 1
            continue
        if control_first_parent_range_contaminated(sampled, all_shas, revert_shas, e, w):
            stats["n_dropped_contaminated"] += 1
            continue
        mx_pos = lead_max_a(a_series, e, w)
        mx_neg = lead_max_a(a_series, e - w, w)
        if mx_pos is None or mx_neg is None:
            stats["n_dropped_no_a"] += 1
            continue
        stats["n_matched"] += 1
        dm_pos = dm_series[e - 1]
        dm_neg = dm_series[e - w - 1]
        mx_dm_pos = lead_max_abs(dm_series, e, w)
        mx_dm_neg = lead_max_abs(dm_series, e - w, w)
        d_dm: float | str = ""
        if mx_dm_pos is not None and mx_dm_neg is not None:
            d_dm = mx_dm_pos - mx_dm_neg
        pairs.append(
            {
                "e": e,
                "max_a_pos": mx_pos,
                "max_a_neg": mx_neg,
                "d_a": mx_pos - mx_neg,
                "max_abs_dm_pos": "" if mx_dm_pos is None else mx_dm_pos,
                "max_abs_dm_neg": "" if mx_dm_neg is None else mx_dm_neg,
                "d_abs_dm": d_dm,
                "m_pos": m_series[e - 1],
                "m_neg": m_series[e - w - 1],
                "abs_dm_pos": abs(dm_pos) if dm_pos is not None else 0.0,
                "abs_dm_neg": abs(dm_neg) if dm_neg is not None else 0.0,
                "rise_pos": mx_pos > 0 and lead_m_ok(m_series, e, w, 1.0),
                "rise_strict_pos": mx_pos > 0 and lead_m_ok(m_series, e, w, 0.5),
                "rise_neg": mx_neg > 0 and lead_m_ok(m_series, e - w, w, 1.0),
            }
        )
    return pairs, stats


def _parse_optional_float(raw: object) -> float | None:
    if raw is None or raw == "":
        return None
    return float(raw)


def median_of(xs: list[float]) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    n = len(ys)
    if n % 2:
        return ys[n // 2]
    return 0.5 * (ys[n // 2 - 1] + ys[n // 2])


def walsh_averages(diffs: list[float]) -> list[float]:
    out: list[float] = []
    n = len(diffs)
    for i in range(n):
        for j in range(i, n):
            out.append(0.5 * (diffs[i] + diffs[j]))
    out.sort()
    return out


def hodges_lehmann(diffs: list[float]) -> float | None:
    if not diffs:
        return None
    return median_of(walsh_averages(diffs))


def _abs_ties(diffs: list[float]) -> bool:
    abs_d = [abs(d) for d in diffs]
    return len(abs_d) != len(set(abs_d))


def wilcoxon_tplus_cdf(n: int, k: int) -> float:
    if n <= 0:
        return 1.0 if k >= 0 else 0.0
    total = 1 << n
    count = 0
    for bits in range(total):
        t = 0
        r = 1
        b = bits
        while r <= n:
            if b & 1:
                t += r
            b >>= 1
            r += 1
        if t <= k:
            count += 1
    return count / total


def walsh_bauer_ci(
    diffs: list[float],
    alpha: float = 0.05,
) -> tuple[float | None, float | None, float | None, str]:
    nz = [d for d in diffs if d != 0.0]
    n = len(nz)
    if n == 0:
        return None, None, None, "no non-zero paired differences"
    if n > 20:
        return None, None, None, "n>20"
    if _abs_ties(nz):
        return None, None, None, "ties"
    wavg = walsh_averages(nz)
    m = len(wavg)
    chosen_k: int | None = None
    attained: float | None = None
    for k in range(0, m):
        p = wilcoxon_tplus_cdf(n, k)
        if 2.0 * p <= alpha + 1e-15:
            chosen_k = k
            attained = 1.0 - 2.0 * p
        else:
            break
    if chosen_k is None:
        p0 = wilcoxon_tplus_cdf(n, 0)
        return wavg[0], wavg[-1], 1.0 - 2.0 * p0, "exact_95_impossible"
    lo = wavg[chosen_k]
    hi = wavg[m - chosen_k - 1]
    return lo, hi, attained, "walsh_bauer"


def wilson_interval(successes: int, n: int) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p = successes / n
    z = Z_WILSON
    z2 = z * z
    den = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / den
    margin = z * math.sqrt((p * (1.0 - p) + z2 / (4.0 * n)) / n) / den
    return max(0.0, center - margin), min(1.0, center + margin)


def bootstrap_hl_ci(
    diffs: list[float],
    *,
    seed: int = BOOT_SEED,
    n_boot: int = BOOT_B,
) -> tuple[float | None, float | None]:
    if len(diffs) < 1:
        return None, None
    rng = random.Random(seed)
    n = len(diffs)
    stats = [hodges_lehmann([diffs[rng.randrange(n)] for _ in range(n)]) for _ in range(n_boot)]
    clean = [x for x in stats if x is not None]
    if not clean:
        return None, None
    clean.sort()
    lo_i = int(math.floor(0.025 * len(clean)))
    hi_i = int(math.ceil(0.975 * len(clean))) - 1
    hi_i = min(max(hi_i, 0), len(clean) - 1)
    return clean[lo_i], clean[hi_i]


def wilcoxon_signed_rank(diffs: list[float]) -> tuple[float | None, float | None, str]:
    nz = [d for d in diffs if d != 0.0]
    n = len(nz)
    if n == 0:
        return None, None, "no non-zero paired differences"
    if n > 20:
        return None, None, "n>20 (exact Wilcoxon not used)"
    abs_d = [abs(d) for d in nz]
    order = sorted(range(n), key=lambda i: abs_d[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs_d[order[j + 1]] == abs_d[order[i]]:
            j += 1
        mid = 0.5 * ((i + 1) + (j + 1))
        for k in range(i, j + 1):
            ranks[order[k]] = mid
        i = j + 1
    t_plus = sum(ranks[i] for i in range(n) if nz[i] > 0)
    mu = n * (n + 1) / 4.0
    obs = abs(t_plus - mu)
    total = 1 << n
    count = 0
    for bits in range(total):
        t = 0.0
        for i in range(n):
            if bits & (1 << i):
                t += ranks[i]
        if abs(t - mu) + 1e-12 >= obs:
            count += 1
    return t_plus, min(1.0, count / total), ""


def contrast_row(
    diffs: list[float],
    *,
    window: str,
    repo: str,
    split: str,
    w: int,
    marker: str,
    role: str,
) -> dict:
    n = len(diffs)
    n_gt = sum(1 for d in diffs if d > 0)
    n_eq = sum(1 for d in diffs if d == 0)
    n_lt = sum(1 for d in diffs if d < 0)
    mean_d = (sum(diffs) / n) if n else None
    med = median_of(diffs)
    hl = hodges_lehmann(diffs)
    exact_lo, exact_hi, attained, exact_note = walsh_bauer_ci(diffs)
    blo, bhi = bootstrap_hl_ci(diffs)
    if exact_note == "walsh_bauer":
        lo, hi, method = exact_lo, exact_hi, "walsh_bauer"
        note = ""
    else:
        lo, hi, method = blo, bhi, "bootstrap"
        note = exact_note
    conc = ((n_gt + 0.5 * n_eq) / n) if n else None
    p_gt = (n_gt / n) if n else None
    wlo, whi = wilson_interval(n_gt, n)
    t_plus, p_w, wnote = wilcoxon_signed_rank(diffs)
    if wnote:
        note = (note + "; " if note else "") + wnote
    if n == 0:
        note = "no matched pairs"
    includes0 = ""
    if lo is not None and hi is not None:
        includes0 = int(lo <= 0.0 <= hi)
    return {
        "window": window,
        "repo": repo,
        "split": split,
        "w": w,
        "marker": marker,
        "role": role,
        "n": n,
        "n_d_gt0": n_gt,
        "n_d_eq0": n_eq,
        "n_d_lt0": n_lt,
        "mean_d": "" if mean_d is None else mean_d,
        "median_d": "" if med is None else med,
        "hodges_lehmann": "" if hl is None else hl,
        "hl_ci95_lo": "" if lo is None else lo,
        "hl_ci95_hi": "" if hi is None else hi,
        "ci_method": method if n else "",
        "exact_attained_coverage": "" if attained is None else attained,
        "hl_includes_0": includes0,
        "concordance": "" if conc is None else conc,
        "p_d_gt0": "" if p_gt is None else p_gt,
        "wilson95_lo": "" if wlo is None else wlo,
        "wilson95_hi": "" if whi is None else whi,
        "wilcoxon_t_plus": "" if t_plus is None else t_plus,
        "wilcoxon_p": "" if p_w is None else p_w,
        "note": note,
    }


CONTRAST_FIELDS = [
    "window",
    "repo",
    "split",
    "w",
    "marker",
    "role",
    "n",
    "n_d_gt0",
    "n_d_eq0",
    "n_d_lt0",
    "mean_d",
    "median_d",
    "hodges_lehmann",
    "hl_ci95_lo",
    "hl_ci95_hi",
    "ci_method",
    "exact_attained_coverage",
    "hl_includes_0",
    "concordance",
    "p_d_gt0",
    "wilson95_lo",
    "wilson95_hi",
    "wilcoxon_t_plus",
    "wilcoxon_p",
    "note",
]

PAIR_FIELDS = [
    "window",
    "repo",
    "split",
    "w",
    "e",
    "max_a_pos",
    "max_a_neg",
    "d_a",
    "max_abs_dm_pos",
    "max_abs_dm_neg",
    "d_abs_dm",
]


def load_v3_series_window(window: dict) -> dict:
    path = RESULTS_V3 / f"series_{window['id']}.csv"
    if not path.is_file():
        raise RuntimeError(f"missing {path}; run --corpus v3 first")
    repo = ensure_clone(window)
    all_shas = first_parent_shas(repo, window["start"], window["end"])
    sampled: list[int] = []
    shas: list[str] = []
    m_series: list[float] = []
    a_series: list[float | None] = []
    dm_series: list[float | None] = []
    events: set[int] = set()
    with path.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            s_i = int(row["sample"])
            sampled.append(int(row["first_parent_index"]))
            shas.append(row["sha"])
            m_series.append(float(row["m"]))
            a_series.append(_parse_optional_float(row.get("a")))
            dm_series.append(_parse_optional_float(row.get("delta_m")))
            if int(row.get("event_sample") or 0) == 1:
                events.add(s_i)
    if sampled:
        series0 = run_git(repo, ["rev-parse", shas[0]]).strip()
        expected0 = all_shas[sampled[0]]
        if series0 != expected0:
            raise RuntimeError(f"{window['id']} series SHA does not match frozen walk")
    revert_shas = revert_shas_for_walk(repo, all_shas)
    return {
        "id": window["id"],
        "name": window["name"],
        "split": window["split"],
        "all_shas": all_shas,
        "sampled": sampled,
        "m_series": m_series,
        "a_series": a_series,
        "dm_series": dm_series,
        "events": sorted(events),
        "revert_shas": sorted(revert_shas),
        "n_first_parent": len(all_shas),
        "n_samples": len(sampled),
        "n_reverts": len(revert_shas),
        "n_event_samples": len(events),
    }


A_SERIES_FIELDS = [
    "sample",
    "m",
    "delta_m",
    "a",
    "m_bin",
    "delta_m_bin",
    "a_bin",
]


def _family_a_payload(i: int) -> bytes:
    return bytes([i % 256]) * 8


def _family_a_write_tree(root: Path, n: int) -> dict[str, str]:
    files: dict[str, str] = {}
    for i in range(n):
        rel = f"f{i:03d}.bin"
        dest = root / rel
        dest.write_bytes(_family_a_payload(i))
        files[rel] = sha256_file(dest)
    return files


def _family_a_flip(root: Path, rel: str) -> str:
    path = root / rel
    path.write_bytes(path.read_bytes() + b"x")
    return sha256_file(path)


def _family_a_rows(m_hist: list[float], m_bin_hist: list[int]) -> list[dict]:
    rows: list[dict] = []
    for i in range(len(m_hist)):
        delta, a = kinematics(m_hist[: i + 1])
        db, ab = kinematics([float(x) for x in m_bin_hist[: i + 1]])
        rows.append(
            {
                "sample": i,
                "m": m_hist[i],
                "delta_m": "" if delta is None else delta,
                "a": "" if a is None else a,
                "m_bin": m_bin_hist[i],
                "delta_m_bin": "" if db is None else db,
                "a_bin": "" if ab is None else ab,
            }
        )
    return rows


def _family_a_record(root: Path, baseline: dict[str, str], live: dict[str, str]) -> tuple[float, int]:
    return public_m(baseline, live), public_m_bin(baseline, live)


def run_family_a_stable(root: Path) -> list[dict]:
    live = _family_a_write_tree(root, 100)
    baseline = dict(live)
    m_hist: list[float] = []
    bin_hist: list[int] = []
    m, mb = _family_a_record(root, baseline, live)
    m_hist.append(m)
    bin_hist.append(mb)
    for rel in list(live)[:10]:
        live[rel] = _family_a_flip(root, rel)
    for _ in range(3):
        m, mb = _family_a_record(root, baseline, live)
        m_hist.append(m)
        bin_hist.append(mb)
    return _family_a_rows(m_hist, bin_hist)


def run_family_a_steady(root: Path) -> list[dict]:
    live = _family_a_write_tree(root, 100)
    baseline = dict(live)
    names = list(live)
    m_hist: list[float] = []
    bin_hist: list[int] = []
    m, mb = _family_a_record(root, baseline, live)
    m_hist.append(m)
    bin_hist.append(mb)
    cursor = 0
    for _ in range(4):
        for rel in names[cursor : cursor + 2]:
            live[rel] = _family_a_flip(root, rel)
        cursor += 2
        m, mb = _family_a_record(root, baseline, live)
        m_hist.append(m)
        bin_hist.append(mb)
    return _family_a_rows(m_hist, bin_hist)


def run_family_a_accel(root: Path) -> list[dict]:
    live = _family_a_write_tree(root, 50)
    baseline = dict(live)
    names = list(live)
    m_hist: list[float] = []
    bin_hist: list[int] = []
    m, mb = _family_a_record(root, baseline, live)
    m_hist.append(m)
    bin_hist.append(mb)
    cursor = 0
    chunk = 1
    while cursor < 50:
        take = min(chunk, 50 - cursor)
        for rel in names[cursor : cursor + take]:
            live[rel] = _family_a_flip(root, rel)
        cursor += take
        chunk *= 2
        m, mb = _family_a_record(root, baseline, live)
        m_hist.append(m)
        bin_hist.append(mb)
    return _family_a_rows(m_hist, bin_hist)


def family_a_t2(rows: list[dict]) -> dict:
    first_m_bin_one = ""
    last_a_pos = ""
    for r in rows:
        if first_m_bin_one == "" and int(r["m_bin"]) == 1:
            first_m_bin_one = r["sample"]
        if r["a"] != "" and float(r["a"]) > 0:
            last_a_pos = r["sample"]
    return {
        "series": "a_accel",
        "first_m_bin_one": first_m_bin_one,
        "last_a_positive": last_a_pos,
    }


def write_outputs_a(outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cip-family-a-") as tmp:
        base = Path(tmp)
        stable_root = base / "stable"
        steady_root = base / "steady"
        accel_root = base / "accel"
        stable_root.mkdir()
        steady_root.mkdir()
        accel_root.mkdir()
        stable = run_family_a_stable(stable_root)
        steady = run_family_a_steady(steady_root)
        accel = run_family_a_accel(accel_root)
    t2 = family_a_t2(accel)
    write_csv(outdir / "series_a_stable.csv", stable, A_SERIES_FIELDS)
    write_csv(outdir / "series_a_steady.csv", steady, A_SERIES_FIELDS)
    write_csv(outdir / "series_a_accel.csv", accel, A_SERIES_FIELDS)
    write_csv(
        outdir / "t2_a_accel.csv",
        [t2],
        ["series", "first_m_bin_one", "last_a_positive"],
    )
    lines = [
        "# Results (family A series)",
        "",
        "Public path-fraction *m* on the same A-stable / A-steady / A-accel generators as `test_synthetic_family_a.py`. Companion to Hartman, *Kinetic Analysis of Informational Disorder*, v2.4 (2026), [doi:10.5281/zenodo.22417058](https://doi.org/10.5281/zenodo.22417058). Methods/results record: [doi:10.5281/zenodo.22655761](https://doi.org/10.5281/zenodo.22655761).",
        "",
        "Protocol completeness, not a new experiment. Flip fractions were not retuned after seeing tables. Do not mix these series into observational T1 (`results/`, `results-v2/`, `results-v3/`, `results-v3c/`).",
        "",
        "## Series",
        "",
        f"- A-stable: {len(stable)} samples (fixed 10% flip, then hold).",
        f"- A-steady: {len(steady)} samples (2% additional flips per sample).",
        f"- A-accel: {len(accel)} samples (doubling new flips, cap 100%).",
        "",
        "## T2 (A-accel only)",
        "",
        f"- First sample with m_bin=1: {t2['first_m_bin_one']}.",
        f"- Last sample with path-fraction a>0: {t2['last_a_positive']}.",
        "",
        "CSVs in `results-a/`.",
    ]
    (outdir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def future_label(events: set[int], i: int, w: int, n: int) -> int:
    for e in range(i + 1, min(i + w, n) + 1):
        if e in events:
            return 1
    return 0


def score_rows(a_series: list[float | None], m_series: list[float], events: set[int], w: int) -> list[dict]:
    n = len(m_series)
    last = n - 1
    rows: list[dict] = []
    for i in range(w, last):
        start = i - w + 1
        if start < 0:
            continue
        vals = [a_series[j] for j in range(start, i + 1) if a_series[j] is not None]
        if not vals:
            continue
        rows.append(
            {
                "i": i,
                "score_a": max(vals),
                "score_m": m_series[i],
                "score_dm": (m_series[i] - m_series[i - 1]) if i >= 1 else 0.0,
                "label": future_label(events, i, w, last),
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def ckpt_maps_path(window_id: str) -> Path:
    return WORK / "ckpt" / f"{window_id}.maps.jsonl"


def load_ckpt_maps(path: Path) -> list[tuple[str, dict[str, str]]]:
    if not path.is_file():
        return []
    out: list[tuple[str, dict[str, str]]] = []
    truncated = False
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                truncated = True
                break
            out.append((str(obj["sha"]), dict(obj["files"])))
    if truncated:
        write_ckpt_maps(path, out)
    return out


def write_ckpt_maps(path: Path, pairs: list[tuple[str, dict[str, str]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for sha, files in pairs:
            fh.write(json.dumps({"sha": sha, "files": files}, separators=(",", ":")) + "\n")
    tmp.replace(path)


def append_ckpt_map(path: Path, sha: str, files: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"sha": sha, "files": files}, separators=(",", ":")) + "\n")
        fh.flush()


def analyze_window(
    window: dict,
    outdir: Path,
    *,
    rolling: bool = False,
    allow_over_cap: bool = False,
    local_b: bool = False,
    wallclock: bool = False,
) -> dict:
    repo = ensure_clone(window)
    start, end = window["start"], window["end"]
    all_shas = first_parent_shas(repo, start, end)
    n_all = len(all_shas)
    if n_all > MAX_FIRST_PARENT and not allow_over_cap:
        raise RuntimeError(
            f"{window['name']}: {n_all} first-parent commits exceeds cap "
            f"{MAX_FIRST_PARENT}. Recorded in CORPUS.md. Do not archive until "
            "the maintainer approves; then pass --allow-over-cap."
        )
    sampled = sample_indices(n_all, K)
    revert_shas = revert_shas_for_walk(repo, all_shas)
    events = set(event_sample_indices(all_shas, sampled, revert_shas))

    series_rows: list[dict] = []
    maps: list[dict[str, str]] = []
    baseline: dict[str, str] | None = None
    m_hist: list[float] = []
    mbin_hist: list[float] = []
    m_roll_hist: list[float] = []
    wall_rows: list[dict] = []
    t3_ok = True
    t3_roll_ok = True
    fields = SERIES_FIELDS_ROLL if rolling else SERIES_FIELDS
    ckpt = ckpt_maps_path(str(window["id"]))
    saved = load_ckpt_maps(ckpt)
    expected0 = all_shas[sampled[0]] if sampled else ""
    if saved and saved[0][0] != expected0:
        print(f"{window['id']} dropping stale checkpoint {ckpt}", flush=True)
        saved = []
        if ckpt.is_file():
            ckpt.unlink()

    for s_i, commit_i in enumerate(sampled):
        sha = all_shas[commit_i]
        if s_i < len(saved) and saved[s_i][0] == sha:
            print(f"{window['id']} sample {s_i + 1}/{len(sampled)} {sha[:12]} (checkpoint)", flush=True)
            live = saved[s_i][1]
        else:
            if s_i < len(saved):
                saved = saved[:s_i]
                write_ckpt_maps(ckpt, saved)
            print(f"{window['id']} sample {s_i + 1}/{len(sampled)} {sha[:12]}", flush=True)
            prev_map = maps[-1] if maps else None
            prev_sha = all_shas[sampled[s_i - 1]] if maps else None
            live = archive_tree(repo, sha, prev_sha=prev_sha, prev_map=prev_map)
            append_ckpt_map(ckpt, sha, live)
            saved.append((sha, live))
        maps.append(live)
        if wallclock:
            unix, iso = committer_meta(repo, sha)
            parent_unix = first_parent_committer_unix(repo, sha)
            hours: float | str = ""
            if wall_rows:
                hours = (unix - int(wall_rows[-1]["committer_unix"])) / 3600.0
            wall_rows.append(
                {
                    "window": window["id"],
                    "repo": window["name"],
                    "sample": s_i,
                    "sha": sha,
                    "committer_unix": unix,
                    "committer_iso": iso,
                    "hours_since_prev_sample": hours,
                    "flag_unix_lt_1": int(unix < 1),
                    "flag_before_first_parent": int(
                        parent_unix is not None and unix < parent_unix
                    ),
                }
            )
        if local_b:
            if s_i == 0:
                n0 = 0
                m = 0.0
                mb = 0.0
                m_log = 0.0
                d_m = None
                a_m = None
                d_b = None
                a_b = None
            else:
                b_prev = maps[-2]
                n0 = len(b_prev)
                m = public_m(b_prev, live)
                mb = float(public_m_bin(b_prev, live))
                statuses = [path_status(b_prev, live, p) for p in b_prev]
                m_log = m_from_log(statuses, n0)
                if abs(m_log - m) > 1e-12:
                    t3_ok = False
            m_hist.append(m)
            mbin_hist.append(mb)
            if s_i > 0:
                d_m, a_m = kinematics(m_hist)
                d_b, a_b = kinematics(mbin_hist)
            row = {
                "sample": s_i,
                "first_parent_index": commit_i,
                "sha": sha,
                "n0": n0,
                "m": m,
                "delta_m": "" if d_m is None else d_m,
                "a": "" if a_m is None else a_m,
                "m_bin": mb,
                "delta_m_bin": "" if d_b is None else d_b,
                "a_bin": "" if a_b is None else a_b,
                "m_from_log": m_log,
                "revert_commit": int(sha in revert_shas),
                "event_sample": int(s_i in events),
            }
        else:
            if baseline is None:
                baseline = dict(live)
            n0 = len(baseline)
            m = public_m(baseline, live)
            mb = float(public_m_bin(baseline, live))
            m_hist.append(m)
            mbin_hist.append(mb)
            d_m, a_m = kinematics(m_hist)
            d_b, a_b = kinematics(mbin_hist)
            statuses = [path_status(baseline, live, p) for p in baseline]
            m_log = m_from_log(statuses, n0)
            if abs(m_log - m) > 1e-12:
                t3_ok = False
            row = {
                "sample": s_i,
                "first_parent_index": commit_i,
                "sha": sha,
                "n0": n0,
                "m": m,
                "delta_m": "" if d_m is None else d_m,
                "a": "" if a_m is None else a_m,
                "m_bin": mb,
                "delta_m_bin": "" if d_b is None else d_b,
                "a_bin": "" if a_b is None else a_b,
                "m_from_log": m_log,
                "revert_commit": int(sha in revert_shas),
                "event_sample": int(s_i in events),
            }
            if rolling:
                roll_i = (s_i // ROLL_EVERY) * ROLL_EVERY
                b_roll = maps[roll_i]
                n0_roll = len(b_roll)
                m_roll = public_m(b_roll, live)
                m_roll_hist.append(m_roll)
                d_mr, a_mr = kinematics(m_roll_hist)
                statuses_roll = [path_status(b_roll, live, p) for p in b_roll]
                m_log_roll = m_from_log(statuses_roll, n0_roll)
                if abs(m_log_roll - m_roll) > 1e-12:
                    t3_roll_ok = False
                row.update(
                    {
                        "roll_baseline_sample": roll_i,
                        "n0_roll": n0_roll,
                        "m_roll": m_roll,
                        "delta_m_roll": "" if d_mr is None else d_mr,
                        "a_roll": "" if a_mr is None else a_mr,
                        "m_from_log_roll": m_log_roll,
                    }
                )
        series_rows.append(row)
        write_csv(outdir / f"series_{window['id']}.csv", series_rows, fields)

    a_series: list[float | None] = []
    dm_series: list[float | None] = []
    for row in series_rows:
        a_series.append(None if row["a"] == "" else float(row["a"]))
        dm_series.append(None if row["delta_m"] == "" else float(row["delta_m"]))
    m_series = [float(r["m"]) for r in series_rows]
    a_series_roll: list[float | None] = []
    m_series_roll: list[float] = []
    if rolling:
        for row in series_rows:
            a_series_roll.append(None if row["a_roll"] == "" else float(row["a_roll"]))
            m_series_roll.append(float(row["m_roll"]))

    t2_first_mbin_one = next((r["sample"] for r in series_rows if float(r["m_bin"]) == 1.0), "")
    last_a_pos = ""
    for row in reversed(series_rows):
        if row["a"] != "" and float(row["a"]) > 0:
            last_a_pos = row["sample"]
            break

    summary = {
        "id": window["id"],
        "name": window["name"],
        "split": window["split"],
        "n_first_parent": n_all,
        "n_samples": len(sampled),
        "n_reverts": len(revert_shas),
        "n_event_samples": len(events),
        "t3_log_equals_rewalk": t3_ok,
        "t3_roll_log_equals_rewalk": t3_roll_ok if rolling else "",
        "t2_first_m_bin_one": t2_first_mbin_one,
        "t2_last_a_positive": last_a_pos,
        "events": sorted(events),
        "sampled": sampled,
        "revert_shas": sorted(revert_shas),
        "all_shas": all_shas,
        "wall_rows": wall_rows,
        "m_series": m_series,
        "a_series": a_series,
        "dm_series": dm_series,
        "m_series_roll": m_series_roll,
        "a_series_roll": a_series_roll,
        "series_rows": series_rows,
        "rolling": rolling,
    }
    fields = SERIES_FIELDS_ROLL if rolling else SERIES_FIELDS
    write_csv(outdir / f"series_{window['id']}.csv", series_rows, fields)
    return summary


def fmt(x: float | None) -> str:
    if x is None:
        return "n/a"
    return f"{x:.6g}"


def t1_table(
    summaries: list[dict],
    *,
    m_key: str,
    a_key: str,
) -> tuple[list[dict], list[str], dict[str, dict[int, list[dict]]]]:
    t1_rows: list[dict] = []
    t1_md: list[str] = []
    score_by_split: dict[str, dict[int, list[dict]]] = {"train": {}, "test": {}}
    for w in LEAD_W:
        score_by_split["train"][w] = []
        score_by_split["test"][w] = []
    for s in summaries:
        events = set(s["events"])
        m_series = s[m_key]
        a_series = s[a_key]
        for w in LEAD_W:
            pos, neg = classify_points(m_series, a_series, events, w)
            n_pos = len(pos)
            n_neg = len(neg)
            pos_rise = sum(1 for r in pos if r["rise"])
            neg_rise = sum(1 for r in neg if r["rise"])
            pos_strict = sum(1 for r in pos if r["rise_strict"])
            t1_rows.append(
                {
                    "window": s["id"],
                    "repo": s["name"],
                    "split": s["split"],
                    "w": w,
                    "n_positive": n_pos,
                    "n_negative": n_neg,
                    "positives_lead_rise": pos_rise,
                    "negatives_lead_rise": neg_rise,
                    "positives_lead_rise_m_lt_0.5": pos_strict,
                }
            )
            t1_md.append(
                f"- {s['name']} w={w}: positives {pos_rise}/{n_pos} lead rise; "
                f"negatives {neg_rise}/{n_neg} lead rise; "
                f"strict (m<0.5) positives {pos_strict}/{n_pos}."
            )
            score_by_split[s["split"]][w].extend(score_rows(a_series, m_series, events, w))
    return t1_rows, t1_md, score_by_split


def write_outputs_v3(
    summaries: list[dict],
    outdir: Path,
    *,
    train_label: str,
    test_label: str,
) -> None:
    t1_rows: list[dict] = []
    t1_md: list[str] = []
    pair_by_split: dict[str, dict[int, list[dict]]] = {"train": {}, "test": {}}
    for w in LEAD_W:
        pair_by_split["train"][w] = []
        pair_by_split["test"][w] = []
    drop_md: list[str] = []
    for s in summaries:
        events = set(s["events"])
        revert_shas = set(s["revert_shas"])
        for w in LEAD_W:
            pairs, stats = matched_pair_rows(
                s["a_series"],
                s["m_series"],
                s["dm_series"],
                events,
                s["sampled"],
                s["all_shas"],
                revert_shas,
                w,
            )
            n_pos = stats["n_matched"]
            pos_rise = sum(1 for p in pairs if p["rise_pos"])
            neg_rise = sum(1 for p in pairs if p["rise_neg"])
            pos_strict = sum(1 for p in pairs if p["rise_strict_pos"])
            t1_rows.append(
                {
                    "window": s["id"],
                    "repo": s["name"],
                    "split": s["split"],
                    "w": w,
                    "n_positive": n_pos,
                    "n_negative": n_pos,
                    "positives_lead_rise": pos_rise,
                    "negatives_lead_rise": neg_rise,
                    "positives_lead_rise_m_lt_0.5": pos_strict,
                    "n_events": stats["n_events"],
                    "n_dropped_short": stats["n_dropped_short"],
                    "n_dropped_contaminated": stats["n_dropped_contaminated"],
                    "n_dropped_no_a": stats["n_dropped_no_a"],
                    "n_matched": stats["n_matched"],
                }
            )
            t1_md.append(
                f"- {s['name']} w={w}: matched {stats['n_matched']}/{stats['n_events']} "
                f"(dropped short {stats['n_dropped_short']}, contaminated "
                f"{stats['n_dropped_contaminated']}, no a {stats['n_dropped_no_a']}); "
                f"positives {pos_rise}/{n_pos} lead rise; "
                f"negatives {neg_rise}/{n_pos} lead rise; "
                f"strict (m<0.5) positives {pos_strict}/{n_pos}."
            )
            for p in pairs:
                pair_by_split[s["split"]][w].extend(
                    [
                        {
                            "score_a": p["max_a_pos"],
                            "score_m": p["m_pos"],
                            "score_dm": p["abs_dm_pos"],
                            "label": 1,
                        },
                        {
                            "score_a": p["max_a_neg"],
                            "score_m": p["m_neg"],
                            "score_dm": p["abs_dm_neg"],
                            "label": 0,
                        },
                    ]
                )
            drop_md.append(
                f"- {s['name']} w={w}: events {stats['n_events']}, matched "
                f"{stats['n_matched']}, dropped short {stats['n_dropped_short']}, "
                f"contaminated {stats['n_dropped_contaminated']}, no a "
                f"{stats['n_dropped_no_a']}."
            )
    write_csv(outdir / "t1_counts.csv", t1_rows, T1_MATCH_FIELDS)

    wall_all: list[dict] = []
    for s in summaries:
        wall_all.extend(s.get("wall_rows") or [])
    if wall_all:
        write_csv(outdir / "wallclock_spacing.csv", wall_all, WALL_FIELDS)

    t2_rows = []
    for s in summaries:
        t2_rows.append(
            {
                "window": s["id"],
                "repo": s["name"],
                "first_sample_m_bin_eq_1": s["t2_first_m_bin_one"],
                "last_sample_path_fraction_a_gt_0": s["t2_last_a_positive"],
            }
        )
    write_csv(
        outdir / "t2_binary.csv",
        t2_rows,
        ["window", "repo", "first_sample_m_bin_eq_1", "last_sample_path_fraction_a_gt_0"],
    )
    t3_rows = [
        {
            "window": s["id"],
            "repo": s["name"],
            "log_equals_rewalk": int(s["t3_log_equals_rewalk"]),
        }
        for s in summaries
    ]
    write_csv(outdir / "t3_log_equality.csv", t3_rows, ["window", "repo", "log_equals_rewalk"])

    op_rows: list[dict] = []
    op_md: list[str] = []
    for w in LEAD_W:
        train = pair_by_split["train"][w]
        test = pair_by_split["test"][w]
        tau_a, train_info = youden_tau([r["score_a"] for r in train], [r["label"] for r in train])
        tau_m, _ = youden_tau([r["score_m"] for r in train], [r["label"] for r in train])
        tau_dm, _ = youden_tau([r["score_dm"] for r in train], [r["label"] for r in train])
        row = {
            "w": w,
            "train_n": train_info.get("n", len(train)),
            "train_positives": train_info.get("positives", sum(r["label"] for r in train)),
            "tau_a": "" if tau_a is None else tau_a,
            "tau_m": "" if tau_m is None else tau_m,
            "tau_abs_dm": "" if tau_dm is None else tau_dm,
            "note": train_info.get("note", ""),
        }

        def _beats(rec_x: float, fpr_x: float, rec_y: float, fpr_y: float) -> bool:
            return (rec_x > rec_y and fpr_x <= fpr_y) or (fpr_x < fpr_y and rec_x >= rec_y)

        if tau_a is not None and test:
            m_a = class_metrics([r["score_a"] for r in test], [r["label"] for r in test], tau_a)
            row.update({f"test_a_{k}": v for k, v in m_a.items()})
        if tau_m is not None and test:
            m_m = class_metrics([r["score_m"] for r in test], [r["label"] for r in test], tau_m)
            row.update({f"test_m_{k}": v for k, v in m_m.items()})
        if tau_dm is not None and test:
            m_d = class_metrics([r["score_dm"] for r in test], [r["label"] for r in test], tau_dm)
            row.update({f"test_dm_{k}": v for k, v in m_d.items()})
        if tau_a is not None and tau_m is not None and test:
            rec_a = float(row.get("test_a_recall", 0))
            rec_m = float(row.get("test_m_recall", 0))
            fpr_a = float(row.get("test_a_false_positive_rate", 1))
            fpr_m = float(row.get("test_m_false_positive_rate", 1))
            beats_m = _beats(rec_a, fpr_a, rec_m, fpr_m)
            row["a_beats_latest_m_on_test"] = int(beats_m)
            rec_d = float(row.get("test_dm_recall", 0)) if tau_dm is not None else 0.0
            fpr_d = float(row.get("test_dm_false_positive_rate", 1)) if tau_dm is not None else 1.0
            beats_d = _beats(rec_a, fpr_a, rec_d, fpr_d) if tau_dm is not None else False
            row["a_beats_abs_delta_m_on_test"] = int(beats_d) if tau_dm is not None else ""
            op_md.append(
                f"- w={w}: train Youden τ_a={fmt(tau_a)}, τ_m={fmt(tau_m)}, "
                f"τ_|Δm|={fmt(tau_dm)}. "
                f"Test recall a={fmt(rec_a)} vs m={fmt(rec_m)} vs |Δm|={fmt(rec_d)}; "
                f"FPR a={fmt(fpr_a)} vs m={fmt(fpr_m)} vs |Δm|={fmt(fpr_d)}. "
                f"{'a beat latest m on this rule' if beats_m else 'a did not beat latest m on this rule'}. "
                f"{'a beat latest |Δm| on this rule' if beats_d else 'a did not beat latest |Δm| on this rule'}. "
                "Operating point on this corpus only; not window-closed. "
                "Matched pairs only."
            )
        else:
            row["a_beats_latest_m_on_test"] = ""
            row["a_beats_abs_delta_m_on_test"] = ""
            op_md.append(
                f"- w={w}: Youden τ not defined or test empty ({train_info.get('note', '')})."
            )
        op_rows.append(row)
    write_csv(outdir / "operating_point.csv", op_rows, sorted({k for r in op_rows for k in r.keys()}))

    n_unix_lt_1 = sum(int(r["flag_unix_lt_1"]) for r in wall_all)
    n_before_parent = sum(int(r["flag_before_first_parent"]) for r in wall_all)
    hours = [float(r["hours_since_prev_sample"]) for r in wall_all if r["hours_since_prev_sample"] != ""]
    hours_md = "n/a"
    if hours:
        hours_md = (
            f"n={len(hours)}, min={min(hours):.6g} h, median="
            f"{sorted(hours)[len(hours)//2]:.6g} h, max={max(hours):.6g} h"
        )

    lines = [
        "# Results (family B v3)",
        "",
        "Public path-fraction *m* on the frozen D1/C1 walks in `CORPUS.md`. Companion to Hartman, *Kinetic Analysis of Informational Disorder*, v2.4 (2026), [doi:10.5281/zenodo.22417058](https://doi.org/10.5281/zenodo.22417058). Methods/results record: [doi:10.5281/zenodo.22655761](https://doi.org/10.5281/zenodo.22655761).",
        "",
        "A revert is an independent git event, not proof that integrity was unrecoverable. Fitted τ is an operating point on this corpus, not window-closed.",
        "",
        "v3 confirmatory: *B* = previous sample; labels = `is_revert_message` only; matched control is sample block *e−2w … e−w−1*; drop if that first-parent range contains a revert-message commit. Do not walk further back. v1 and v2 stay as published (`results/`, `results-v2/`).",
        "",
        "Time index is sample number at *k* = 25, not wall-clock. Wall-clock hours are reported as spacing only. This study does not interpolate *m*, *Δm*, or *a* onto a calendar grid.",
        "",
        "## Family A",
        "",
        "Synthetic methods check: `python -m pytest test_synthetic_family_a.py`. A-stable and A-steady give *a* near 0; A-accel gives *a* > 0 before *m* saturates. Family A remains that pytest check; this directory has no family A series CSV.",
        "",
        "## T1 observational counts (local B, matched negatives)",
        "",
    ]
    lines.extend(t1_md)
    lines.extend(["", "## Matched-pair drop counts", ""])
    lines.extend(drop_md)
    lines.extend(["", "## T2 binary vs path-fraction (local B)", ""])
    for s in summaries:
        lines.append(
            f"- {s['name']}: first sample with m_bin=1 is {s['t2_first_m_bin_one']}; "
            f"last sample with path-fraction a>0 is {s['t2_last_a_positive']}."
        )
    lines.extend(["", "## T3 log equals re-walk (local B)", ""])
    for s in summaries:
        lines.append(f"- {s['name']}: {'pass' if s['t3_log_equals_rewalk'] else 'FAIL'}.")
    lines.extend(["", f"## Operating point (train {train_label}, test {test_label}, matched pairs)", ""])
    lines.extend(op_md)
    lines.extend(
        [
            "",
            "## Wall-clock spacing (not interpolated into a)",
            "",
            f"- samples with unix time < 1: {n_unix_lt_1}.",
            f"- samples with committer stamp earlier than first-parent: {n_before_parent}.",
            f"- hours between consecutive samples: {hours_md}.",
            "",
            "## Window sizes",
            "",
        ]
    )
    for s in summaries:
        lines.append(
            f"- {s['name']}: {s['n_first_parent']} first-parent commits, "
            f"{s['n_samples']} samples (k={K}), {s['n_reverts']} revert-message commits, "
            f"{s['n_event_samples']} event samples."
        )
    lines.extend(["", "CSVs in `results-v3/`."])
    (outdir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    skip = (
        "series_rows",
        "m_series",
        "a_series",
        "dm_series",
        "m_series_roll",
        "a_series_roll",
        "all_shas",
        "wall_rows",
    )
    (outdir / "summary.json").write_text(
        json.dumps([{k: v for k, v in s.items() if k not in skip} for s in summaries], indent=2)
        + "\n",
        encoding="utf-8",
    )


def _fmt_ci_note(note: str) -> str:
    parts: list[str] = []
    for raw in [p.strip() for p in note.split(";") if p.strip()]:
        if raw == "ties":
            parts.append("Walsh/Bauer skipped (ties); bootstrap 95% used")
        elif raw == "exact_95_impossible":
            parts.append("exact 95% inversion impossible; bootstrap 95% used")
        elif raw == "n>20":
            parts.append("n>20; bootstrap 95% used")
        elif raw == "n>20 (exact Wilcoxon not used)":
            parts.append("n>20 (exact Wilcoxon not used)")
        else:
            parts.append(raw)
    return ". ".join(parts)


def _fmt_contrast_line(row: dict) -> str:
    n = int(row["n"])
    if n == 0:
        return f"- {row['repo']} w={row['w']} ({row['role']}): no matched pairs."
    hl = row["hodges_lehmann"]
    lo = row["hl_ci95_lo"]
    hi = row["hl_ci95_hi"]
    inc = row["hl_includes_0"]
    inc_txt = "interval includes 0" if inc == 1 else "interval excludes 0"
    p = row["wilcoxon_p"]
    extra = ""
    if row["exact_attained_coverage"] != "":
        extra += (
            f"; exact attained coverage "
            f"{fmt(row['exact_attained_coverage'] if row['exact_attained_coverage'] != '' else None)}"
        )
    note_txt = _fmt_ci_note(str(row["note"] or ""))
    if note_txt:
        extra += f". {note_txt}."
    else:
        extra += "."
    return (
        f"- {row['repo']} w={row['w']} ({row['role']}): n={n}, d>0 {row['n_d_gt0']}, "
        f"d=0 {row['n_d_eq0']}, d<0 {row['n_d_lt0']}; "
        f"Hodges-Lehmann {fmt(hl if hl != '' else None)} "
        f"(95% {row['ci_method']} {fmt(lo if lo != '' else None)} to "
        f"{fmt(hi if hi != '' else None)}, {inc_txt}); "
        f"concordance {fmt(row['concordance'] if row['concordance'] != '' else None)}; "
        f"P(d>0) {fmt(row['p_d_gt0'] if row['p_d_gt0'] != '' else None)} "
        f"(Wilson 95% {fmt(row['wilson95_lo'] if row['wilson95_lo'] != '' else None)} to "
        f"{fmt(row['wilson95_hi'] if row['wilson95_hi'] != '' else None)}); "
        f"Wilcoxon T+={fmt(row['wilcoxon_t_plus'] if row['wilcoxon_t_plus'] != '' else None)}, "
        f"p={fmt(p if p != '' else None)}"
        + extra
    )


def write_outputs_v3c(summaries: list[dict], outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    contrast_rows: list[dict] = []
    pair_rows: list[dict] = []
    drop_md: list[str] = []
    a_md: list[str] = []
    dm_md: list[str] = []
    for s in summaries:
        events = set(s["events"])
        revert_shas = set(s["revert_shas"])
        role = "descriptive" if s["split"] == "train" else "confirmatory"
        for w in LEAD_W:
            pairs, stats = matched_pair_rows(
                s["a_series"],
                s["m_series"],
                s["dm_series"],
                events,
                s["sampled"],
                s["all_shas"],
                revert_shas,
                w,
            )
            drop_md.append(
                f"- {s['name']} w={w}: events {stats['n_events']}, matched "
                f"{stats['n_matched']}, dropped short {stats['n_dropped_short']}, "
                f"contaminated {stats['n_dropped_contaminated']}, no a "
                f"{stats['n_dropped_no_a']}."
            )
            for p in pairs:
                pair_rows.append(
                    {
                        "window": s["id"],
                        "repo": s["name"],
                        "split": s["split"],
                        "w": w,
                        "e": p["e"],
                        "max_a_pos": p["max_a_pos"],
                        "max_a_neg": p["max_a_neg"],
                        "d_a": p["d_a"],
                        "max_abs_dm_pos": p["max_abs_dm_pos"],
                        "max_abs_dm_neg": p["max_abs_dm_neg"],
                        "d_abs_dm": p["d_abs_dm"],
                    }
                )
            d_a = [float(p["d_a"]) for p in pairs]
            d_dm = [float(p["d_abs_dm"]) for p in pairs if p["d_abs_dm"] != ""]
            a_row = contrast_row(
                d_a,
                window=s["id"],
                repo=s["name"],
                split=s["split"],
                w=w,
                marker="max_a",
                role=role,
            )
            dm_row = contrast_row(
                d_dm,
                window=s["id"],
                repo=s["name"],
                split=s["split"],
                w=w,
                marker="max_abs_dm",
                role=role,
            )
            contrast_rows.append(a_row)
            contrast_rows.append(dm_row)
            a_md.append(_fmt_contrast_line(a_row))
            dm_md.append(_fmt_contrast_line(dm_row))
    write_csv(outdir / "matched_pairs.csv", pair_rows, PAIR_FIELDS)
    write_csv(outdir / "continuous_contrast.csv", contrast_rows, CONTRAST_FIELDS)
    lines = [
        "# Results (family B v3c)",
        "",
        "Public path-fraction *m* on the frozen D1/C1 walks in `CORPUS.md`. Companion to Hartman, *Kinetic Analysis of Informational Disorder*, v2.4 (2026), [doi:10.5281/zenodo.22417058](https://doi.org/10.5281/zenodo.22417058). Methods/results record: [doi:10.5281/zenodo.22655761](https://doi.org/10.5281/zenodo.22655761).",
        "",
        "v3c continuous contrast of the frozen v3 matched pairs. v3 sign-test tables stay in `results-v3/`. v1 and v2 stay as published (`results/`, `results-v2/`).",
        "",
        "Pairwise *d_a* is lead-window max *a* on the event block minus max *a* on the matched control. Primary estimand is the Hodges-Lehmann estimator of *d_a*. Prefer Walsh/Bauer 95% endpoints; bootstrap (B=10000, seed 20260908) if ties or discreteness prevent exact 95% inversion. Fitted τ is not used. django/django is descriptive; python/cpython is confirmatory. A revert is an independent git event, not proof that integrity was unrecoverable. If the Hodges-Lehmann 95% interval includes 0, magnitudes do not separate on this rule.",
        "",
        "Time index is sample number at *k* = 25, not wall-clock. This study does not interpolate *m*, *Δm*, or *a* onto a calendar grid.",
        "",
        "## Family A",
        "",
        "Synthetic methods check: `python -m pytest test_synthetic_family_a.py`. Family A remains that pytest check; this directory has no family A series CSV.",
        "",
        "## Matched-pair drop counts (same rule as v3)",
        "",
    ]
    lines.extend(drop_md)
    lines.extend(["", "## Primary: paired max a (Hodges-Lehmann of d_a)", ""])
    lines.extend(a_md)
    lines.extend(["", "## Secondary: paired max |Δm| (not mixed into primary)", ""])
    lines.extend(dm_md)
    lines.extend(["", "## Window sizes", ""])
    for s in summaries:
        lines.append(
            f"- {s['name']}: {s['n_first_parent']} first-parent commits, "
            f"{s['n_samples']} samples (k={K}), {s['n_reverts']} revert-message commits, "
            f"{s['n_event_samples']} event samples."
        )
    lines.extend(["", "CSVs in `results-v3c/`."])
    (outdir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    skip = ("all_shas", "sampled", "m_series", "a_series", "dm_series")
    (outdir / "summary.json").write_text(
        json.dumps([{k: v for k, v in s.items() if k not in skip} for s in summaries], indent=2)
        + "\n",
        encoding="utf-8",
    )


def write_outputs(
    summaries: list[dict],
    outdir: Path,
    *,
    corpus: str,
    train_label: str,
    test_label: str,
    csv_dir_name: str,
) -> None:
    if corpus == "v3c":
        write_outputs_v3c(summaries, outdir)
        return
    if corpus == "a":
        write_outputs_a(outdir)
        return
    if corpus == "v3":
        write_outputs_v3(summaries, outdir, train_label=train_label, test_label=test_label)
        return
    t1_rows, t1_md, score_by_split = t1_table(summaries, m_key="m_series", a_key="a_series")
    write_csv(outdir / "t1_counts.csv", t1_rows, T1_FIELDS)

    t1_roll_md: list[str] = []
    if any(s.get("rolling") for s in summaries):
        t1_roll_rows, t1_roll_md, _ = t1_table(
            summaries, m_key="m_series_roll", a_key="a_series_roll"
        )
        write_csv(outdir / "t1_counts_rolling.csv", t1_roll_rows, T1_FIELDS)

    t2_rows = []
    for s in summaries:
        t2_rows.append(
            {
                "window": s["id"],
                "repo": s["name"],
                "first_sample_m_bin_eq_1": s["t2_first_m_bin_one"],
                "last_sample_path_fraction_a_gt_0": s["t2_last_a_positive"],
            }
        )
    write_csv(
        outdir / "t2_binary.csv",
        t2_rows,
        ["window", "repo", "first_sample_m_bin_eq_1", "last_sample_path_fraction_a_gt_0"],
    )

    t3_rows = [
        {
            "window": s["id"],
            "repo": s["name"],
            "log_equals_rewalk": int(s["t3_log_equals_rewalk"]),
        }
        for s in summaries
    ]
    write_csv(outdir / "t3_log_equality.csv", t3_rows, ["window", "repo", "log_equals_rewalk"])

    op_rows: list[dict] = []
    op_md: list[str] = []
    for w in LEAD_W:
        train = score_by_split["train"][w]
        test = score_by_split["test"][w]
        tau_a, train_info = youden_tau([r["score_a"] for r in train], [r["label"] for r in train])
        tau_m, _ = youden_tau([r["score_m"] for r in train], [r["label"] for r in train])
        row = {
            "w": w,
            "train_n": train_info.get("n", len(train)),
            "train_positives": train_info.get("positives", sum(r["label"] for r in train)),
            "tau_a": "" if tau_a is None else tau_a,
            "tau_m": "" if tau_m is None else tau_m,
            "note": train_info.get("note", ""),
        }
        if tau_a is not None and test:
            m_a = class_metrics([r["score_a"] for r in test], [r["label"] for r in test], tau_a)
            row.update({f"test_a_{k}": v for k, v in m_a.items()})
        if tau_m is not None and test:
            m_m = class_metrics([r["score_m"] for r in test], [r["label"] for r in test], tau_m)
            row.update({f"test_m_{k}": v for k, v in m_m.items()})
        if tau_a is not None and tau_m is not None and test:
            rec_a = row.get("test_a_recall", 0)
            rec_m = row.get("test_m_recall", 0)
            fpr_a = row.get("test_a_false_positive_rate", 1)
            fpr_m = row.get("test_m_false_positive_rate", 1)
            beats = (rec_a > rec_m and fpr_a <= fpr_m) or (fpr_a < fpr_m and rec_a >= rec_m)
            row["a_beats_latest_m_on_test"] = int(beats)
            op_md.append(
                f"- w={w}: train Youden τ_a={fmt(tau_a)}, τ_m={fmt(tau_m)}. "
                f"Test recall a={fmt(float(rec_a))} vs m={fmt(float(rec_m))}; "
                f"FPR a={fmt(float(fpr_a))} vs m={fmt(float(fpr_m))}. "
                f"{'a beat latest m on this rule' if beats else 'a did not beat latest m on this rule'}. "
                "Operating point on this corpus only; not window-closed."
            )
        else:
            row["a_beats_latest_m_on_test"] = ""
            op_md.append(
                f"- w={w}: Youden τ not defined or test empty ({train_info.get('note', '')})."
            )
        op_rows.append(row)
    write_csv(outdir / "operating_point.csv", op_rows, sorted({k for r in op_rows for k in r.keys()}))

    v1_note = ""
    grain_note = ""
    family_a_note = (
        "Synthetic methods check: `python -m pytest test_synthetic_family_a.py`. "
        "A-stable and A-steady give *a* near 0; A-accel gives *a* > 0 before *m* saturates."
    )
    if corpus == "v2":
        v1_note = (
            " v1 tag windows (Flask 2.0.0-3.0.0 train, HTTPie 3.0.0-3.2.4 test) remain "
            "the published miss: 0 revert-message commits, Youden undefined. See `results/`."
        )
        grain_note = (
            "\n\nv2 T1 lead-rise counts are saturated on both classes: every scored "
            "positive and every scored negative has max *a* > 0 in the lead window under "
            "the locked criterion. Path-fraction *a* did not beat latest *m* on the "
            "pre-declared test rule. A revert-message label is a proxy, not window-closed."
            "\n\nTime index is sample number at *k* = 25 first-parent commits, not "
            "wall-clock. This study does not interpolate calendar time."
            "\n\nv2 positives used `is_revert_message` only (subject `^revert` or body "
            "`this reverts`). Git-graph revert structure was not scored. Negatives were "
            "other samples in the same calendar window, not separate equal-length "
            "no-revert windows."
            "\n\nObservational maps hash `git archive` tar bytes (`digest_git_tar` / "
            "`archive_tree`). Unchanged paths may reuse the prior sample SHA-256 via "
            "`git diff-tree -r --no-renames --name-status`. Family A uses "
            "`public_m.digest_tree` on synthetic trees."
        )
        family_a_note += (
            " Family A remains that pytest check; this directory has no family A series CSV."
        )
    lines = [
        f"# Results (family B {corpus})",
        "",
        "Public path-fraction *m* on the frozen windows in `CORPUS.md`. Companion to Hartman, *Kinetic Analysis of Informational Disorder*, v2.4 (2026), [doi:10.5281/zenodo.22417058](https://doi.org/10.5281/zenodo.22417058).",
        "",
        "A revert is an independent git event, not proof that integrity was unrecoverable. Fitted τ is an operating point on this corpus, not window-closed."
        + v1_note
        + grain_note,
        "",
        "## Family A",
        "",
        family_a_note,
        "",
        "## T1 observational counts (fixed B = sample 0)",
        "",
    ]
    lines.extend(t1_md)
    if t1_roll_md:
        lines.extend(
            [
                "",
                f"## T1 observational counts (secondary: reset B every {ROLL_EVERY} samples)",
                "",
                "Not mixed into the primary T1 table.",
                "",
            ]
        )
        lines.extend(t1_roll_md)
    lines.extend(["", "## T2 binary vs path-fraction", ""])
    for s in summaries:
        lines.append(
            f"- {s['name']}: first sample with m_bin=1 is {s['t2_first_m_bin_one']}; "
            f"last sample with path-fraction a>0 is {s['t2_last_a_positive']}."
        )
    lines.extend(["", "## T3 log equals re-walk", ""])
    for s in summaries:
        lines.append(f"- {s['name']}: {'pass' if s['t3_log_equals_rewalk'] else 'FAIL'}.")
    lines.extend(["", f"## Operating point (train {train_label}, test {test_label})", ""])
    lines.extend(op_md)
    lines.extend(["", "## Window sizes", ""])
    for s in summaries:
        lines.append(
            f"- {s['name']}: {s['n_first_parent']} first-parent commits, "
            f"{s['n_samples']} samples (k={K}), {s['n_reverts']} revert-message commits, "
            f"{s['n_event_samples']} event samples."
        )
    lines.extend(["", f"CSVs in `{csv_dir_name}/`."])
    (outdir / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    skip = ("series_rows", "m_series", "a_series", "m_series_roll", "a_series_roll")
    (outdir / "summary.json").write_text(
        json.dumps([{k: v for k, v in s.items() if k not in skip} for s in summaries], indent=2)
        + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Family B observational run")
    parser.add_argument(
        "--corpus",
        choices=("v1", "v2", "v3", "v3c", "a"),
        default="v1",
        help="v1 writes results/. v2 writes results-v2/. v3 writes results-v3/. v3c writes results-v3c/ from frozen v3 series (paired max a). a writes results-a/ (family A series).",
    )
    parser.add_argument(
        "--allow-over-cap",
        action="store_true",
        help="Permit git archive when a window exceeds 2000 first-parent commits.",
    )
    args = parser.parse_args()
    if args.corpus == "a":
        write_outputs_a(RESULTS_A)
        print("wrote", RESULTS_A, flush=True)
        return 0
    if args.corpus == "v1":
        windows = WINDOWS_V1
        outdir = RESULTS_V1
        rolling = False
        local_b = False
        wallclock = False
        train_label = "flask"
        test_label = "HTTPie"
        csv_dir_name = "results"
    elif args.corpus == "v2":
        windows = WINDOWS_V2
        outdir = RESULTS_V2
        rolling = True
        local_b = False
        wallclock = False
        train_label = "django"
        test_label = "CPython"
        csv_dir_name = "results-v2"
    elif args.corpus == "v3c":
        windows = WINDOWS_V2
        outdir = RESULTS_V3C
        rolling = False
        local_b = True
        wallclock = False
        train_label = "django"
        test_label = "CPython"
        csv_dir_name = "results-v3c"
    else:
        windows = WINDOWS_V2
        outdir = RESULTS_V3
        rolling = False
        local_b = True
        wallclock = True
        train_label = "django"
        test_label = "CPython"
        csv_dir_name = "results-v3"
    if args.corpus == "v3c":
        outdir.mkdir(parents=True, exist_ok=True)
        summaries = [load_v3_series_window(w) for w in windows]
        write_outputs(
            summaries,
            outdir,
            corpus="v3c",
            train_label=train_label,
            test_label=test_label,
            csv_dir_name=csv_dir_name,
        )
        print("wrote", outdir, flush=True)
        return 0
    if not args.allow_over_cap:
        over: list[str] = []
        for w in windows:
            repo = ensure_clone(w)
            n = len(first_parent_shas(repo, w["start"], w["end"]))
            if n > MAX_FIRST_PARENT:
                over.append(f"{w['name']}: {n}")
        if over:
            raise RuntimeError(
                "first-parent count exceeds cap "
                f"{MAX_FIRST_PARENT} ({'; '.join(over)}). "
                "Recorded in CORPUS.md. Do not archive until the maintainer "
                "approves; then pass --allow-over-cap."
            )
    outdir.mkdir(parents=True, exist_ok=True)
    summaries = [
        analyze_window(
            w,
            outdir,
            rolling=rolling,
            allow_over_cap=args.allow_over_cap,
            local_b=local_b,
            wallclock=wallclock,
        )
        for w in windows
    ]
    write_outputs(
        summaries,
        outdir,
        corpus=args.corpus,
        train_label=train_label,
        test_label=test_label,
        csv_dir_name=csv_dir_name,
    )
    print("wrote", outdir, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

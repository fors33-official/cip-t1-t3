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
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

from public_m import (
    kinematics,
    m_from_log,
    path_status,
    public_m,
    public_m_bin,
)

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "corpus-work"
RESULTS_V1 = ROOT / "results"
RESULTS_V2 = ROOT / "results-v2"
K = 25
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
    for row in series_rows:
        a_series.append(None if row["a"] == "" else float(row["a"]))
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
        "m_series": m_series,
        "a_series": a_series,
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


def write_outputs(
    summaries: list[dict],
    outdir: Path,
    *,
    corpus: str,
    train_label: str,
    test_label: str,
    csv_dir_name: str,
) -> None:
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
        choices=("v1", "v2"),
        default="v1",
        help="v1 writes results/ (published miss). v2 writes results-v2/.",
    )
    parser.add_argument(
        "--allow-over-cap",
        action="store_true",
        help="Permit git archive when a window exceeds 2000 first-parent commits.",
    )
    args = parser.parse_args()
    if args.corpus == "v1":
        windows = WINDOWS_V1
        outdir = RESULTS_V1
        rolling = False
        train_label = "flask"
        test_label = "HTTPie"
        csv_dir_name = "results"
    else:
        windows = WINDOWS_V2
        outdir = RESULTS_V2
        rolling = True
        train_label = "django"
        test_label = "CPython"
        csv_dir_name = "results-v2"
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
        analyze_window(w, outdir, rolling=rolling, allow_over_cap=args.allow_over_cap)
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

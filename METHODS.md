# Methods (T1–T3)

Companion to Hartman, *Kinetic Analysis of Informational Disorder*, v2.4 (2026), Section 7. Frozen 7 September 2026. Do not change these rules after observational labels are inspected.

## Scope

Use only this public *m*. Do not use a withheld production estimator. Do not use customer trees or unpublished corpora. Ignore `.git/` and other VCS metadata. Directories are not hashed as files.

Family A digests files on disk with `public_m.digest_tree` / `public_m.sha256_file` (SHA-256 of file bytes). Observational family B materializes trees with `git archive --format=tar` and hashes file bytes from the tar (`digest_git_tar` in `run_family_b.py`). After the first sample, unchanged paths may reuse the prior sample hash when `git diff-tree -r --no-renames --name-status` reports no change; that is the same SHA-256 as a full re-archive of those paths.

Baseline *B* is the tree at sample 0 of that series. Do not slide *B* in the primary analysis.

Primary denominator: baseline-only (*N_0* from *B*). Missing baseline paths count as mismatch.

## Labels

**Family A (synthetic).** Start from a public tree at *B*. Three series:

- A-stable: flip a fixed 10% of baseline paths and leave them flipped. Expect *a* near 0.
- A-steady: each sample, flip 2% additional previously unflipped baseline paths. Expect *a* near 0 and constant *Δm*.
- A-accel: each sample, flip twice as many new paths as the previous sample, cap at 100%. Expect *a* > 0 before *m* saturates at 1.

Family A is implemented in `test_synthetic_family_a.py`. If A fails, the implementation of *m* is wrong. Do not proceed to observational T1. Family A in this tree is that pytest check; no family A series CSV is published.

**Family B (observational).** Public git histories, one series per window listed in `CORPUS.md`. The intended positive event is a commit whose message or git graph is a revert of a prior commit in the window. v1 and v2 scored positives with `is_revert_message` only (subject `^revert` or body `this reverts`). Git-graph revert structure was not scored. The intended negatives are equal-length windows with no revert. v2 used other samples in the same calendar window as negatives. Report families separately. A revert is an independent operational event, not proof that integrity was unrecoverable.

Lead definition: for a positive event at sample *e*, inspect *a* on *e−w … e−1* with *w* = 5 and *w* = 10, both reported. “Rise before saturation” means max *a* in that lead window is > 0 and *m* at those samples is < 1 (stricter table: *m* < 0.5).

## T1, T2, T3

**T1.** Family A is the pytest check above. On family B, contrast lead-window max *a* before a revert vs the negatives as run. Report counts: *n* windows, positives with a lead rise, negatives with a lead rise.

**T2.** On the same samples, compute *a* from path-fraction *m* and from binary *m*. After the first mismatch, binary *m* is 1 under a fixed baseline and its *a* is 0 thereafter.

**T3.** Reconstruct a baseline file (path, SHA-256) at sample 0 and a per-path log at later samples (`unchanged` / `changed` / `missing`). *m_n* computed only from those log lines must equal *m_n* from a re-walk of the tree.

## Fitted threshold

If a threshold τ on lead-window max *a* is reported, it is an **operating point** on this corpus, not window-closed. Split observational windows **by whole repository**, not by sample (one train repo, one test repo; not a 70/30 sample split). Pre-declare the rule (Youden on ROC). Freeze τ. Evaluate on test against a baseline that uses only latest *m* (or *Δm*). If *a* does not beat latest *m* on test, that is the result.

## Sampling

Materialize trees with `git archive` at each sampled commit. Walk **first-parent** history from the start SHA to the end SHA. Sample every **25th** first-parent commit (*k* = 25), plus the start and end commits. Time index is sample number, not wall-clock. This study does not interpolate calendar gaps. Sampling every commit on a large repo is not required.

## What would not count

- Internal product runs with no public *m* and no public trees.
- Labeling windows with *a* and then testing *a*.
- Presenting a fitted τ as window-closed or as a universal constant.
- Changing path filters, *m*, or *w* after looking at the revert table.
- Importing cosmology preprints into this study.

## Corpus v2 (locked 7 September 2026, before v2 SHA freeze)

v1 tag windows stay as published. Do not slide F1/H1. v2 does not change *m*, the revert rule, or *k*.

- Same public *m* (baseline-only SHA-256 path fraction). Same *k* = 25.
- Revert labels as run: `is_revert_message` only. Git-graph revert was not scored.
- Negatives as run: other samples in the same calendar window, not separate equal-length no-revert windows.
- Train/test: whole repository. Pre-declared in `CORPUS.md`: django/django train, python/cpython test.
- Primary T1: fixed *B* = sample 0 of that window. Do not slide *B*.
- Secondary table (not mixed into primary T1): reset *B* every 20 samples. Same labels and *w*. Report separately.
- Youden τ remains an operating point, not window-closed.
- First-parent commit count is recorded at freeze. CPython 2023 exceeded 2000 first-parent commits; the v2 archive ran with `--allow-over-cap` after that waiver. Do not replace a remote by revert density.

## Corpus v3 (locked 7 September 2026, not started)

Do not extend `CORPUS.md` or inspect new revert counts until a later run is approved against this freeze. v1 and v2 stay as published. Do not slide v2 SHAs, *k*, or public *m*. If a run is later approved, extend `run_family_b.py` only.

- Independent equal-length no-revert windows. Do not reuse other samples inside an event window as the matched negatives.
- Revert labels: git-graph revert of a prior commit in the window plus the message regex, or message-only stated as message-only before SHAs.
- Primary *B* is local (previous sample, or a pre-declared rolling window shorter than the full series). Do not mix a v3 table into v2 CSVs.
- Optional robustness, pre-declared before SHAs: denser *k*, or wall-clock spacing with a declared interpolation rule.
- Public trees only. Same public *m*. No withheld production estimator.

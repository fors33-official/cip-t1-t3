# Methods (T1–T3)

Companion to Hartman, *Kinetic Analysis of Informational Disorder*, v2.4 (2026), Section 7. Frozen 7 September 2026. Do not change these rules after observational labels are inspected.

## Scope

Use only this public *m*. Do not use a withheld production estimator. Do not use customer trees or unpublished corpora. Ignore `.git/` and other VCS metadata. Directories are not hashed as files.

Digest: SHA-256 of file bytes (`public_m.digest_tree`, `public_m.sha256_file`).

Baseline *B* is the tree at sample 0 of that series. Do not slide *B* in the primary analysis.

Primary denominator: baseline-only (*N_0* from *B*). Missing baseline paths count as mismatch.

## Labels

**Family A (synthetic).** Start from a public tree at *B*. Three series:

- A-stable: flip a fixed 10% of baseline paths and leave them flipped. Expect *a* near 0.
- A-steady: each sample, flip 2% additional previously unflipped baseline paths. Expect *a* near 0 and constant *Δm*.
- A-accel: each sample, flip twice as many new paths as the previous sample, cap at 100%. Expect *a* > 0 before *m* saturates at 1.

Family A is implemented in `test_synthetic_family_a.py`. If A fails, the implementation of *m* is wrong. Do not proceed to observational T1.

**Family B (observational).** Public git histories, one series per window listed in `CORPUS.md`. Primary positive event: a commit whose message or graph is a revert of a prior commit in the window (`git revert` / “This reverts”). Negative windows: same repos, equal-length windows with no revert. Report families separately. A revert is an independent operational event, not proof that integrity was unrecoverable.

Lead definition: for a positive event at sample *e*, inspect *a* on *e−w … e−1* with *w* = 5 and *w* = 10, both reported. “Rise before saturation” means max *a* in that lead window is > 0 and *m* at those samples is < 1 (stricter table: *m* < 0.5).

## T1, T2, T3

**T1.** Publish family A series. On family B, contrast lead-window max *a* before a revert vs matched negatives. Report counts: *n* windows, positives with a lead rise, negatives with a lead rise.

**T2.** On the same samples, compute *a* from path-fraction *m* and from binary *m*. After the first mismatch, binary *m* is 1 under a fixed baseline and its *a* is 0 thereafter.

**T3.** Reconstruct a baseline file (path, SHA-256) at sample 0 and a per-path log at later samples (`unchanged` / `changed` / `missing`). *m_n* computed only from those log lines must equal *m_n* from a re-walk of the tree.

## Fitted threshold

If a threshold τ on lead-window max *a* is reported, it is an **operating point** on this corpus, not window-closed. Split observational windows train/test 70/30 **by repository**, not by sample. Pre-declare the rule (Youden on ROC). Freeze τ. Evaluate on test against a baseline that uses only latest *m* (or *Δm*). If *a* does not beat latest *m* on test, that is the result.

## Sampling

Materialize trees with `git archive` at each sampled commit. Walk **first-parent** history from the start SHA to the end SHA. Sample every **25th** first-parent commit (*k* = 25), plus the start and end commits. Sampling every commit on a large repo is not required.

## What would not count

- Internal product runs with no public *m* and no public trees.
- Labeling windows with *a* and then testing *a*.
- Presenting a fitted τ as window-closed or as a universal constant.
- Changing path filters, *m*, or *w* after looking at the revert table.
- Importing cosmology preprints into this study.

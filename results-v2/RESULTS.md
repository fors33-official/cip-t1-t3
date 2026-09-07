# Results (family B v2)

Public path-fraction *m* on the frozen windows in `CORPUS.md`. Companion to Hartman, *Kinetic Analysis of Informational Disorder*, v2.4 (2026), [doi:10.5281/zenodo.22417058](https://doi.org/10.5281/zenodo.22417058).

A revert is an independent git event, not proof that integrity was unrecoverable. Fitted τ is an operating point on this corpus, not window-closed. v1 tag windows (Flask 2.0.0-3.0.0 train, HTTPie 3.0.0-3.2.4 test) remain the published miss: 0 revert-message commits, Youden undefined. See `results/`.

v2 T1 lead-rise counts are saturated on both classes: every scored positive and every scored negative has max *a* > 0 in the lead window under the locked criterion. Path-fraction *a* did not beat latest *m* on the pre-declared test rule. A revert-message label is a proxy, not window-closed.

Time index is sample number at *k* = 25 first-parent commits, not wall-clock. This study does not interpolate calendar time.

v2 positives used `is_revert_message` only (subject `^revert` or body `this reverts`). Git-graph revert structure was not scored. Negatives were other samples in the same calendar window, not separate equal-length no-revert windows.

Observational maps hash `git archive` tar bytes (`digest_git_tar` / `archive_tree`). Unchanged paths may reuse the prior sample SHA-256 via `git diff-tree -r --no-renames --name-status`. Family A uses `public_m.digest_tree` on synthetic trees.

## Family A

Synthetic methods check: `python -m pytest test_synthetic_family_a.py`. A-stable and A-steady give *a* near 0; A-accel gives *a* > 0 before *m* saturates. Family A remains that pytest check; this directory has no family A series CSV.

## T1 observational counts (fixed B = sample 0)

- django/django w=5: positives 9/9 lead rise; negatives 26/26 lead rise; strict (m<0.5) positives 9/9.
- django/django w=10: positives 8/8 lead rise; negatives 22/22 lead rise; strict (m<0.5) positives 8/8.
- python/cpython w=5: positives 23/23 lead rise; negatives 151/151 lead rise; strict (m<0.5) positives 18/23.
- python/cpython w=10: positives 22/22 lead rise; negatives 147/147 lead rise; strict (m<0.5) positives 17/22.

## T1 observational counts (secondary: reset B every 20 samples)

Not mixed into the primary T1 table.

- django/django w=5: positives 9/9 lead rise; negatives 26/26 lead rise; strict (m<0.5) positives 9/9.
- django/django w=10: positives 8/8 lead rise; negatives 22/22 lead rise; strict (m<0.5) positives 8/8.
- python/cpython w=5: positives 23/23 lead rise; negatives 151/151 lead rise; strict (m<0.5) positives 23/23.
- python/cpython w=10: positives 22/22 lead rise; negatives 147/147 lead rise; strict (m<0.5) positives 22/22.

## T2 binary vs path-fraction

- django/django: first sample with m_bin=1 is 1; last sample with path-fraction a>0 is 39.
- python/cpython: first sample with m_bin=1 is 1; last sample with path-fraction a>0 is 176.

## T3 log equals re-walk

- django/django: pass.
- python/cpython: pass.

## Operating point (train django, test CPython)

- w=5: train Youden τ_a=0.00781133, τ_m=0.0812678. Test recall a=0.181818 vs m=0.943182; FPR a=0.152941 vs m=1. a did not beat latest m on this rule. Operating point on this corpus only; not window-closed.
- w=10: train Youden τ_a=0.00285414, τ_m=0.119273. Test recall a=0.781513 vs m=0.94958; FPR a=0.714286 vs m=1. a did not beat latest m on this rule. Operating point on this corpus only; not window-closed.

## Window sizes

- django/django: 966 first-parent commits, 40 samples (k=25), 11 revert-message commits, 9 event samples.
- python/cpython: 4442 first-parent commits, 179 samples (k=25), 26 revert-message commits, 24 event samples.

CSVs in `results-v2/`.

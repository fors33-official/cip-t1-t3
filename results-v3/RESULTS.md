# Results (family B v3)

Public path-fraction *m* on the frozen D1/C1 walks in `CORPUS.md`. Companion to Hartman, *Kinetic Analysis of Informational Disorder*, v2.4 (2026), [doi:10.5281/zenodo.22417058](https://doi.org/10.5281/zenodo.22417058). Methods/results record: [doi:10.5281/zenodo.22655761](https://doi.org/10.5281/zenodo.22655761).

A revert is an independent git event, not proof that integrity was unrecoverable. Fitted τ is an operating point on this corpus, not window-closed.

v3 confirmatory: *B* = previous sample; labels = `is_revert_message` only; matched control is sample block *e−2w … e−w−1*; drop if that first-parent range contains a revert-message commit. Do not walk further back. v1 and v2 stay as published (`results/`, `results-v2/`).

Time index is sample number at *k* = 25, not wall-clock. Wall-clock hours are reported as spacing only. This study does not interpolate *m*, *Δm*, or *a* onto a calendar grid.

## Family A

Synthetic methods check: `python -m pytest test_synthetic_family_a.py`. A-stable and A-steady give *a* near 0; A-accel gives *a* > 0 before *m* saturates. Family A remains that pytest check; this directory has no family A series CSV.

## T1 observational counts (local B, matched negatives)

- django/django w=5: matched 4/9 (dropped short 1, contaminated 4, no a 0); positives 4/4 lead rise; negatives 4/4 lead rise; strict (m<0.5) positives 4/4.
- django/django w=10: matched 0/9 (dropped short 7, contaminated 2, no a 0); positives 0/0 lead rise; negatives 0/0 lead rise; strict (m<0.5) positives 0/0.
- python/cpython w=5: matched 8/24 (dropped short 2, contaminated 14, no a 0); positives 8/8 lead rise; negatives 8/8 lead rise; strict (m<0.5) positives 8/8.
- python/cpython w=10: matched 4/24 (dropped short 5, contaminated 15, no a 0); positives 4/4 lead rise; negatives 4/4 lead rise; strict (m<0.5) positives 4/4.

## Matched-pair drop counts

- django/django w=5: events 9, matched 4, dropped short 1, contaminated 4, no a 0.
- django/django w=10: events 9, matched 0, dropped short 7, contaminated 2, no a 0.
- python/cpython w=5: events 24, matched 8, dropped short 2, contaminated 14, no a 0.
- python/cpython w=10: events 24, matched 4, dropped short 5, contaminated 15, no a 0.

## T2 binary vs path-fraction (local B)

- django/django: first sample with m_bin=1 is 1; last sample with path-fraction a>0 is 39.
- python/cpython: first sample with m_bin=1 is 1; last sample with path-fraction a>0 is 177.

## T3 log equals re-walk (local B)

- django/django: pass.
- python/cpython: pass.

## Operating point (train django, test CPython, matched pairs)

- w=5: train Youden τ_a=0.0184321, τ_m=0.0408654, τ_|Δm|=0.0264662. Test recall a=0.25 vs m=0.125 vs |Δm|=0.125; FPR a=0.5 vs m=0 vs |Δm|=0. a did not beat latest m on this rule. a did not beat latest |Δm| on this rule. Operating point on this corpus only; not window-closed. Matched pairs only.
- w=10: Youden τ not defined or test empty (Youden undefined (need both classes)).

## Wall-clock spacing (not interpolated into a)

- samples with unix time < 1: 0.
- samples with committer stamp earlier than first-parent: 0.
- hours between consecutive samples: n=217, min=0 h, median=50.2553 h, max=406.313 h.

## Window sizes

- django/django: 966 first-parent commits, 40 samples (k=25), 11 revert-message commits, 9 event samples.
- python/cpython: 4442 first-parent commits, 179 samples (k=25), 26 revert-message commits, 24 event samples.

CSVs in `results-v3/`.

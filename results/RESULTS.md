# Results (family B)

Public path-fraction *m* on the frozen windows in `CORPUS.md`. Companion to Hartman, *Kinetic Analysis of Informational Disorder*, v2.4 (2026), [doi:10.5281/zenodo.22417058](https://doi.org/10.5281/zenodo.22417058).

A revert is an independent git event, not proof that integrity was unrecoverable. Fitted τ is an operating point on this corpus, not window-closed.

## Family A

Synthetic methods check: `python -m pytest test_synthetic_family_a.py`. A-stable and A-steady give *a* near 0; A-accel gives *a* > 0 before *m* saturates.

## T1 observational counts

These tag-to-tag windows contain no `git revert` / "This reverts" commits, so T1 has no positive class. Negative lead windows often have max *a* > 0: path-fraction *m* versus a fixed baseline moves as the projects grow. That is a result. Do not slide `CORPUS.md`.

- pallets/flask w=5: positives 0/0 lead rise; negatives 6/7 lead rise; strict (m<0.5) positives 0/0.
- pallets/flask w=10: positives 0/0 lead rise; negatives 2/2 lead rise; strict (m<0.5) positives 0/0.
- httpie/cli w=5: positives 0/0 lead rise; negatives 5/5 lead rise; strict (m<0.5) positives 0/0.
- httpie/cli w=10: positives 0/0 lead rise; negatives 0/0 lead rise; strict (m<0.5) positives 0/0.

## T2 binary vs path-fraction

- pallets/flask: first sample with m_bin=1 is 1; last sample with path-fraction a>0 is 9.
- httpie/cli: first sample with m_bin=1 is 1; last sample with path-fraction a>0 is 8.

## T3 log equals re-walk

- pallets/flask: pass.
- httpie/cli: pass.

## Operating point (train flask, test HTTPie)

- w=5: Youden τ not defined or test empty (Youden undefined (need both classes)).
- w=10: Youden τ not defined or test empty (Youden undefined (need both classes)).

## Window sizes

- pallets/flask: 274 first-parent commits, 12 samples (k=25), 0 revert-message commits, 0 event samples.
- httpie/cli: 204 first-parent commits, 10 samples (k=25), 0 revert-message commits, 0 event samples.

CSVs in `results/`.

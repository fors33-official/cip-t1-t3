# CIP T1–T3 public mismatch analysis

Methods and synthetic checks for public mismatch level *m* as defined in Hartman, *Kinetic Analysis of Informational Disorder*, v2.4 (2026). This analysis record: [https://doi.org/10.5281/zenodo.22655761](https://doi.org/10.5281/zenodo.22655761). Working paper: [https://doi.org/10.5281/zenodo.22417058](https://doi.org/10.5281/zenodo.22417058). Glossary: [https://doi.org/10.5281/zenodo.22499313](https://doi.org/10.5281/zenodo.22499313).

This repository is analysis code and tables for that paper. It is not Fors33 commercial software. It does not implement or disclose a production estimator of *m*.

**Publisher:** Fors33, Inc.  
**Status:** family A (synthetic) and family B (observational tables) are in this tree. Family B **v1** tag windows (Flask 2.0.0-3.0.0 train, HTTPie 3.0.0-3.2.4 test) found **zero** revert-message commits, so T1 has no positives and Youden τ is undefined. See `RESULTS.md` (copied from `results/RESULTS.md`). Family B **v2** calendar windows (django/django train, python/cpython test) have revert-message commits; T1 lead-rise is saturated on both classes; fitted τ is an operating point, not window-closed; path-fraction *a* did not beat latest *m* on the pre-declared test rule. See `results-v2/RESULTS.md`. Family B **v3** is a confirmatory analysis of the same frozen D1/C1 walks: *B* = previous sample; matched preceding-block negatives with a drop rule; labels remain `is_revert_message` only. Remaining matched pairs still have lead-rise on both classes; *a* did not beat latest *m* or latest *|Δm|* on the pre-declared test rule at *w* = 5; *w* = 10 train matched 0 so Youden is undefined. Time index is sample number at *k* = 25, not wall-clock; wall-clock hours are spacing only (no interpolation). See `results-v3/RESULTS.md`. Do not slide `CORPUS.md` after that inspection.

## Public *m*

At sample *n*, *m_n* is the fraction of **baseline** paths whose SHA-256 differs from the baseline digest, or that are missing. *N_0* is fixed from baseline *B*. New paths that were not in *B* do not enter the denominator. Time index is sample number, not wall-clock.

- *Δm_n = m_n − m_{n−1}* (undefined until two samples)
- *a_n = Δm_n − Δm_{n−1}* (undefined until three samples)

Binary *m* is 0 if every baseline path matches, else 1.

## Run the methods check

```
python -m pytest test_synthetic_family_a.py
```

Requires pytest. Expected: A-stable and A-steady give *a* near 0; A-accel gives *a* > 0 before *m* reaches 1; *a* is undefined until three samples.

Observational family B (after family A):

```
python run_family_b.py
```

`python run_family_b.py` (or `--corpus v1`) writes `results/` and does not touch later result dirs. `--corpus v2` writes `results-v2/` (rolling *B* every 20 samples as a secondary table). `--corpus v3` writes `results-v3/` (local *B* = previous sample; matched negatives; wall-clock spacing CSV). CPython 2023 exceeds 2000 first-parent commits; this tree already ran v2 and v3 with `--allow-over-cap` as compute-only. Clones listed remotes into gitignored `corpus-work/`. Checkpoints live under `corpus-work/ckpt/` (gitignored). Frozen windows are in `CORPUS.md`.

## License

Code in this repository is MIT (see `LICENSE`). The working paper and glossary remain CC BY 4.0 on Zenodo. Neither license covers unpublished implementations or Fors33 commercial software.

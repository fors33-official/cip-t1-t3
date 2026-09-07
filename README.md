# CIP T1–T3 public mismatch analysis

Methods and synthetic checks for public mismatch level *m* as defined in Hartman, *Kinetic Analysis of Informational Disorder*, v2.4 (2026). Working paper: [https://doi.org/10.5281/zenodo.22417058](https://doi.org/10.5281/zenodo.22417058). Glossary: [https://doi.org/10.5281/zenodo.22499313](https://doi.org/10.5281/zenodo.22499313).

This repository is analysis code and tables for that paper. It is not Fors33 commercial software. It does not implement or disclose a production estimator of *m*.

**Publisher:** Fors33, Inc.  
**Status:** family A (synthetic) is in this tree. Observational family B is not run until the windows in `CORPUS.md` are materialized under the rules in `METHODS.md`.

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

## License

Code in this repository is MIT (see `LICENSE`). The working paper and glossary remain CC BY 4.0 on Zenodo. Neither license covers unpublished implementations or Fors33 commercial software.

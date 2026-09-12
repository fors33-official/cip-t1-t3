# Results (family B v3c)

Public path-fraction *m* on the frozen D1/C1 walks in `CORPUS.md`. Companion to Hartman, *Kinetic Analysis of Informational Disorder*, v2.4 (2026), [doi:10.5281/zenodo.22417058](https://doi.org/10.5281/zenodo.22417058). Methods/results record: [doi:10.5281/zenodo.22655761](https://doi.org/10.5281/zenodo.22655761).

v3c continuous contrast of the frozen v3 matched pairs. v3 sign-test tables stay in `results-v3/`. v1 and v2 stay as published (`results/`, `results-v2/`). This directory closes the public git-revert T1 series (v1–v3c). These tables test live-branch path-fraction *a* before revert-message commits. They are a methods check for the working paper, not a general lead-time result and not a product test. Do not treat a later denser-*k* or new-remote walk as a patch to these tables.

Pairwise *d_a* is lead-window max *a* on the event block minus max *a* on the matched control. Primary estimand is the Hodges-Lehmann estimator of *d_a*. Prefer Walsh/Bauer 95% endpoints; bootstrap (B=10000, seed 20260908) if ties or discreteness prevent exact 95% inversion. Fitted τ is not used. django/django is descriptive; python/cpython is confirmatory. A revert is an independent git event, not proof that integrity was unrecoverable. If the Hodges-Lehmann 95% interval includes 0, magnitudes do not separate on this rule.

Time index is sample number at *k* = 25, not wall-clock. This study does not interpolate *m*, *Δm*, or *a* onto a calendar grid.

## Family A

Synthetic methods check: `python -m pytest test_synthetic_family_a.py`. Family A remains that pytest check; this directory has no family A series CSV.

## Matched-pair drop counts (same rule as v3)

- django/django w=5: events 9, matched 4, dropped short 1, contaminated 4, no a 0.
- django/django w=10: events 9, matched 0, dropped short 7, contaminated 2, no a 0.
- python/cpython w=5: events 24, matched 8, dropped short 2, contaminated 14, no a 0.
- python/cpython w=10: events 24, matched 4, dropped short 5, contaminated 15, no a 0.

## Primary: paired max a (Hodges-Lehmann of d_a)

- django/django w=5 (descriptive): n=4, d>0 4, d=0 0, d<0 0; Hodges-Lehmann 0.0193983 (95% bootstrap 0.0095097 to 0.0327439, interval excludes 0); concordance 1; P(d>0) 1 (Wilson 95% 0.510109 to 1); Wilcoxon T+=10, p=0.125. Walsh/Bauer skipped (ties); bootstrap 95% used.
- django/django w=10 (descriptive): no matched pairs.
- python/cpython w=5 (confirmatory): n=8, d>0 2, d=0 0, d<0 6; Hodges-Lehmann -0.00265607 (95% walsh_bauer -0.0124543 to 0.0162151, interval includes 0); concordance 0.25; P(d>0) 0.25 (Wilson 95% 0.0714792 to 0.590725); Wilcoxon T+=14, p=0.640625; exact attained coverage 0.960938.
- python/cpython w=10 (confirmatory): n=4, d>0 1, d=0 0, d<0 3; Hodges-Lehmann -0.00385309 (95% bootstrap -0.00897201 to 0.00625698, interval includes 0); concordance 0.25; P(d>0) 0.25 (Wilson 95% 0.0455873 to 0.699358); Wilcoxon T+=2, p=0.375; exact attained coverage 0.875. exact 95% inversion impossible; bootstrap 95% used.

## Secondary: paired max |Δm| (not mixed into primary)

- django/django w=5 (descriptive): n=4, d>0 4, d=0 0, d<0 0; Hodges-Lehmann 0.0100535 (95% bootstrap 0.00460899 to 0.016702, interval excludes 0); concordance 1; P(d>0) 1 (Wilson 95% 0.510109 to 1); Wilcoxon T+=10, p=0.125; exact attained coverage 0.875. exact 95% inversion impossible; bootstrap 95% used.
- django/django w=10 (descriptive): no matched pairs.
- python/cpython w=5 (confirmatory): n=8, d>0 2, d=0 0, d<0 6; Hodges-Lehmann -0.00433624 (95% walsh_bauer -0.00875153 to 0.0181695, interval includes 0); concordance 0.25; P(d>0) 0.25 (Wilson 95% 0.0714792 to 0.590725); Wilcoxon T+=15, p=0.742188; exact attained coverage 0.960938.
- python/cpython w=10 (confirmatory): n=4, d>0 1, d=0 0, d<0 3; Hodges-Lehmann -0.00535179 (95% bootstrap -0.00782259 to 0.0234061, interval includes 0); concordance 0.25; P(d>0) 0.25 (Wilson 95% 0.0455873 to 0.699358); Wilcoxon T+=4, p=0.875; exact attained coverage 0.875. exact 95% inversion impossible; bootstrap 95% used.

## Window sizes

- django/django: 966 first-parent commits, 40 samples (k=25), 11 revert-message commits, 9 event samples.
- python/cpython: 4442 first-parent commits, 179 samples (k=25), 26 revert-message commits, 24 event samples.

CSVs in `results-v3c/`.

# Frozen observational windows

Frozen 7 September 2026, **before** revert labels are inspected. Do not add, drop, or slide these SHAs after that inspection.

This repository is the small public tree for synthetic overlay and for T3 logs that can be published in full. Observational windows below are independent public projects. They are not Fors33 software.

Sampling rule (see `METHODS.md`): first-parent history, every 25th commit, plus the listed endpoints. Ignore `.git/`.

## Window F1: pallets/flask

- Remote: `https://github.com/pallets/flask.git`
- Start (tag 2.0.0, peeled commit): `2f0c62f5e6e290843f03c1fa70817c7a3c7fd661`
- End (tag 3.0.0): `735a4701d6d5e848241e7d7535db898efb62d400`

## Window H1: httpie/cli

- Remote: `https://github.com/httpie/cli.git`
- Start (tag 3.0.0): `88140422a9d6585a7edfb2c265ebed5d0736df2c`
- End (tag 3.2.4): `2105caa49bae87c5809c274e407619a0de2639d1`

## Train / test split (v1)

When family B v1 is run: assign whole repositories, not samples. Pre-declared: flask is train, httpie/cli is test. Do not reverse that assignment after labels are seen.

## Corpus v2 (calendar 2023)

Frozen 7 September 2026, after the `METHODS.md` Corpus v2 lock, **before** revert-message inspection. Do not add, drop, or slide these SHAs after that inspection. v1 windows F1 and H1 above stay as published.

Bounds: default-branch first-parent. Git `--after="2023-01-01 00:00:00 +0000"` `--before="2024-01-01 00:00:00 +0000"` only. Start is the first listed commit; end is the last.

First-parent counts below are commit counts in that walk, not revert counts. Archive cap is 2000 first-parent commits (see `METHODS.md`). If a window exceeds the cap, do not run `git archive` until the maintainer says to proceed. Do not replace a remote by revert density.

### Window D1: django/django (train)

- Remote: `https://github.com/django/django.git`
- Default branch at freeze: `main`
- Start: `174d8157b5700f6451ac0bdc3eef7e73121bc4a4`
- End: `d88ec42bd0a37340c8477a6f20bf26e58bd84735`
- First-parent commits in window: 966

### Window C1: python/cpython (test)

- Remote: `https://github.com/python/cpython.git`
- Default branch at freeze: `main`
- Start: `1f6c87ca7b9351b2e5c5363504796fce0554c9b8` (committer stamp `2022-12-31 19:01:44 -0500`, which is `2023-01-01 00:01:44 +0000`)
- End: `2849cbb53afc8c6a4465f1b3490c67c2455caf6f`
- First-parent commits in window: 4442

C1 exceeds the 2000 first-parent cap. Stop before archives.

### Train / test split (v2)

Whole repositories, not samples. Pre-declared: django/django is train, python/cpython is test. Do not reverse that assignment after labels are seen.

## Corpus v3 (same D1/C1 walks)

v3 is a new analysis of the frozen D1 and C1 first-parent walks above. It does not add, drop, or slide those SHAs. No new remotes and no new calendar bounds. Start/end remain:

- D1 django/django: `174d8157b5700f6451ac0bdc3eef7e73121bc4a4` … `d88ec42bd0a37340c8477a6f20bf26e58bd84735` (966 first-parent commits)
- C1 python/cpython: `1f6c87ca7b9351b2e5c5363504796fce0554c9b8` … `2849cbb53afc8c6a4465f1b3490c67c2455caf6f` (4442 first-parent commits)

Train/test unchanged: django/django train, python/cpython test. This section does not record revert counts. See `METHODS.md` Corpus v3 for local *B*, matched negatives, and wall-clock reporting (no interpolation).

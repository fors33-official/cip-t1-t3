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

## Train / test split

When family B is run: assign whole repositories, not samples. Pre-declared: flask is train, httpie/cli is test. Do not reverse that assignment after labels are seen.

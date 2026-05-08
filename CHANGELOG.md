# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0a0] — 2026-05-07

### Added

- Algebra of trajectories on `ProfileTrajectory` (eight new methods):
  `velocities`, `accelerations`, `drift`, `volatility`,
  `path_length_per_axis`, `rolling_mean`, `rolling_std`, and a
  per-axis `summary` reporting `n_total`, `n_defined`, `mean`, `std`,
  `drift`, `volatility`, `path_length`. Every primitive preserves the
  mosaic-dropout policy of Autonometrics: `None` propagates through
  differences but never aborts aggregations.
- `CSVTrajectoryAdapter`: load a `ProfileTrajectory` from a CSV with
  canonical axis columns (`closure`, `memory`, `constraint`,
  `persistence`, `coherence`). Empty cells become `None`, missing
  columns yield fully-undefined axes, extra columns are ignored.
  Optional `order_column` sorts rows numerically before construction.
- `BatchTrajectoryAdapter`: build several parallel `ProfileTrajectory`
  objects from grouped profiles, with a `mean_summary` that averages
  per-axis summary metrics across groups (excluding `None` from the
  numerator and denominator).
- Pre-registration document
  [`docs/TRAJECTORY_DIAGNOSTICS.md`](docs/TRAJECTORY_DIAGNOSTICS.md):
  five locked decisions (saturation theorem, named boundary regimes,
  trailing rolling-window contract, volatility-on-velocities, mosaic
  fielty), four predicted outcomes, verdict positive.
- Reproducible test fixture
  `tests/fixtures/autonometrics_v0_8_sample.csv` (15-row public subset
  of the Autonometrics `v0.8.0a0` benchmark) plus
  `tests/fixtures/README.md` documenting origin and reproduction
  recipe.
- Reproducible end-to-end example
  [`examples/trajectory_demo.py`](examples/trajectory_demo.py)
  exercising both adapters on the bundled fixture.
- 100 new tests across `tests/test_algebra.py`,
  `tests/test_diagnostics.py` and `tests/test_adapters.py`. Total
  test count: 119 passed.

### Changed

- `autodynamics-demo` CLI accepts a new optional
  `--report {default,summary}` flag. The default mode is unchanged.

### Notes

- Public API in this release is the trio of v0.1.x
  (`ProfileTrajectory`, `ProfileSnapshot`, `ProfileDelta`) plus the
  two new adapters (`CSVTrajectoryAdapter`,
  `BatchTrajectoryAdapter`). Anything else is internal and may change
  without notice.
- The package keeps its "recording substrate plus algebra" framing.
  No theoretical claims about trajectories, attractors or regimes
  beyond the pre-registered saturation theorem are made or implied.

## [0.1.0a1] — 2026-05-07

### Changed

- README no longer hyperlinks the (now-private) Ex-Machina repository
  and the Citation section asks to cite Autodynamics directly instead
  of the trilogy as a whole. No code, no API, no behaviour changes vs.
  `0.1.0a0`; this is a metadata-only release because PyPI does not
  allow re-uploading the same `(name, version)` filename after fixes.

## [0.1.0a0] — 2026-05-05

### Added

- Initial pre-alpha release.
- `ProfileTrajectory`: a recording substrate that stores a sequence of
  `autonometrics.AutonomyProfile` values, exposes axis-wise time series,
  computes pairwise consecutive deltas, and sums the resulting magnitudes
  into a total path length in profile space.
- `ProfileSnapshot`: a frozen dataclass for a single profile measurement.
- `ProfileDelta`: a frozen dataclass for the difference between two
  consecutive snapshots, with a Euclidean magnitude over its defined axes.
- CLI entry point `autodynamics-demo` (`python -m autodynamics.demo`).
- Runtime dependency on `autonometrics>=0.9.0a0`.
- Reserves the `autodynamics` name on PyPI.
- Declares the project's scope as Layer 2 of the
  Autonometrics -> Autodynamics -> Ex-Machina trilogy.
- Apache License 2.0.

### Notes

- `ProfileTrajectory` is a *recording substrate*, not a theory of
  autonomy dynamics. Disclaimer in README applies.
- Public API in this release is the trio
  (`ProfileTrajectory`, `ProfileSnapshot`, `ProfileDelta`). Anything
  else is internal and may change without notice.

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0a0] — 2026-05-09

### Added

- New submodule `autodynamics.coupling` exposing pairwise Granger
  causality primitives uniformly over the axes of a
  `ProfileTrajectory` (or any `Mapping[str, Sequence[float | None]]`):
  `granger_coupling` (pairwise), `granger_graph` (graph-level entry
  point), and the result types `CausalCouplingResult` and
  `CausalCouplingGraph`. Implements an Augmented Dickey-Fuller
  stationarity gate, up to two automatic differences, AIC-selected
  VAR with `max_lag` configurable, and an F-test on the
  selected-lag coefficients (Granger 1969; Sims 1980;
  Lütkepohl 2005).
- Four scalar diagnostics on the coupling graph: `symmetry_ratio`
  (mean min/max F-stat over unordered pairs), `density` (fraction of
  edges above a threshold or per-edge F critical value),
  `max_in_strength` and `max_out_strength` (maximum F-stat among
  incoming/outgoing edges of an axis). All four return `None`
  rather than raise when no admitted edge has a finite F-stat.
- Mosaic-dropout-fielty axis admission: per-axis longest-contiguous
  run extraction, configurable `mosaic_threshold` (default `0.8`),
  `n_min` length gate (default `50`), `saturation_tol` constant
  detection (default `1e-12`), with explicit reasons in
  `CausalCouplingGraph.excluded_axes`. `None` and `NaN` are handled
  identically.
- Pre-registration document
  [`docs/COUPLING_DIAGNOSTICS.md`](docs/COUPLING_DIAGNOSTICS.md):
  seven locked decisions (pairwise protocol, length and lag
  thresholds, mosaic-dropout policy, pair admission, named boundary
  regimes, diagnostics aggregate semantics) and four predicted
  outcomes (determinism, causality direction recovery on synthetic
  AR pairs, no false-positive flood on independent series, mosaic
  fielty preservation). Verdict positive.
- Public validation document
  [`docs/COUPLING_VALIDATION.md`](docs/COUPLING_VALIDATION.md):
  pre-registered Granger experiment over the 31 groups of the
  Autonometrics `v0.8.0a0` benchmark. **Verdict: REJECTED** by a
  single group (15 of 31 groups admit ≥ 2 axes, against a 50 %
  threshold; the pipeline produces finite F-statistics on 93 % of
  admitted edges, but the source zoo's saturation pattern keeps
  half of its groups below the two-axis admission bar).
- Reproducible validation script
  [`examples/coupling_validation.py`](examples/coupling_validation.py).
- 52 new tests across `tests/test_coupling_smoke.py` (11 smoke
  tests) and `tests/test_coupling.py` (41 behavioural tests). Total
  test count: 171 passed.

### Changed

- `pyproject.toml`: declared dependencies on `scipy>=1.10` and
  `statsmodels>=0.14` (used by the coupling protocol). Added
  `granger-causality` and `coupling-analysis` keywords for PyPI
  search.
- README: new "Coupling analysis" section documenting the public
  API; new entry in "Public validation track" recording the
  REJECTED verdict; layer-2 row of the trilogy table updated to
  mention pairwise coupling.

### Notes

- This is a feature release. The recording substrate, trajectory
  algebra, and adapter API of `0.2.x` are unchanged. All 119 tests
  from the previous release continue to pass alongside the 52 new
  tests.
- `__version__` bumped from `0.2.1a0` to `0.3.0a0`.

## [0.2.1a0] — 2026-05-07

### Changed

- PyPI summary description shortened from the long form shipped in
  `0.2.0a0` ("Modelling autonomy dynamics over the Autonometrics
  atlas. Ships a ProfileTrajectory recording substrate, a small
  algebra of trajectories ...") to the concise
  "Modelling autonomy dynamics over the Autonometrics atlas." The
  short form renders as one line in PyPI search results.
- README roadmap simplified. Future cycles are no longer
  pre-declared. The current scope (algebra primitives, generic
  adapters, pre-registered diagnostics, public validation track) is
  treated as a stable feature set; further development will be
  motivated by a concrete pre-registered design document or external
  collaboration.
- README Vision, toy-demo disclaimer, “Public validation track” intro,
  trajectory-algebra lead paragraph, and layer-2 row of the trilogy
  table reworded so the public narrative matches the stable-scope
  stance: mechanical toolkit, no claimed dynamical theory, honest
  signposting of negative validation outcomes (without altering
  pre-registered `docs/`).
- Documentation softened on `docs/TRAJECTORY_DIAGNOSTICS.md` and
  `docs/TURBULENCE_RANKING.md`: references to unannounced future
  cycles and to specific successor programmes have been replaced by
  scope-of-current-cycle phrasing. Pre-registered LDs, POs and
  verdicts are unchanged.
- Source-code docstrings on `src/autodynamics/trajectory.py` and
  `src/autodynamics/adapters/batch.py` updated for the same reason.

### Notes

- This is a documentation-and-metadata release. No public API
  surface changes vs `0.2.0a0`; all 119 tests continue to pass
  unchanged.
- `__version__` bumped from `0.2.0a0` to `0.2.1a0` so that PyPI
  accepts the corrected metadata; PyPI does not allow re-uploading
  an already-published `(name, version)` filename.

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

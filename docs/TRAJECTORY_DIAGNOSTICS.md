# Trajectory diagnostics

**Status**: pre-registration. Locked at the start of the
`v0.2.0a0` cycle, before any of the implementation report below was
written.

**Cycle**: `v0.2.0a0` (recording substrate + algebra primitives).

**Predecessor design documents**: none. This is the first design
document Autodynamics ships, in the spirit of the Autonometrics
`docs/RAI.md`, `docs/CBA.md` and `docs/ATLAS_GEOMETRY.md`
pre-registration cycle.

---

## Why this document exists

`v0.1.0a1` shipped the smallest honest piece of code that lets a
caller treat a sequence of `autonometrics.AutonomyProfile` values as
a trajectory in a metric space: store the sequence, read it axis by
axis, compute pairwise consecutive deltas and sum the resulting
magnitudes into a total path length. That is a *recording substrate*,
not a theory.

`v0.2.0a0` extends the substrate with **algebra primitives** —
velocities, accelerations, drift, volatility, per-axis path length,
trailing rolling mean and rolling std, and a one-shot per-axis
`summary()`. None of these primitives is a discovery. They are the
discrete-calculus toolbox a caller needs to ask the trajectory
elementary geometric questions:

- "Did this axis go anywhere on net?" (`drift`)
- "Was the journey jagged or smooth?" (`volatility`, `path_length`)
- "What was the local slope around timestep `i`?" (`rolling_mean`)

Because the toolbox is so elementary, it is also easy to misread its
output. A caller who runs `volatility()` on a five-snapshot trajectory
and gets `0.0` may not know whether they have observed a stable
system, a saturated boundary, or an artefact of the trajectory being
too short for the metric to mean anything.

This document fixes the **domain of applicability** of every primitive
*before* the implementation, so that future readers can audit the
implementation against a written specification rather than against
tribal knowledge.

The discipline is borrowed wholesale from Autonometrics: every claim
the package will eventually make about real data has to survive a
written, falsifiable specification.

---

## What this cycle is *not*

This cycle is deliberately conservative. It registers exactly one
non-trivial empirical claim — a **theorem of saturation**, which is a
property of the implementation, not of any system the trajectory is
recording. It does *not*:

- discover dynamic regimes,
- name attractors,
- predict transitions,
- claim correlation structure across axes that survives across systems.

Those claims are out of scope. They are not made in this cycle, and
will only be added if and when an explicit pre-registered design
document is shipped.

---

## Locked decisions

### LD-1. Saturation theorem

**Statement.** Let `T` be a `ProfileTrajectory` of length `n >= 2`
in which every snapshot has the same `AutonomyProfile`. For every
axis `a` configured on `T`:

- `T.velocities(a)` is a list of `n - 1` zeros (or `None`s, if the
  axis is `None` in every snapshot).
- `T.path_length_per_axis()[a]` is `0.0` (or `None`).
- `T.volatility(a)` is `0.0` (or `None`).
- `T.drift(a)` is `0.0` (or `None`).

**Verification threshold.** Equality at the floating-point level with
absolute tolerance `1e-12`.

**Falsifiable counter-claim.** If any of the values above is
non-zero on a strictly saturated trajectory, the implementation has a
numerical bug. The cycle does not ship.

### LD-2. Boundary regimes (named)

| Regime              | Definition                                          | Expected behaviour                                                                                                                                |
|---------------------|-----------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|
| **Empty**           | `len(T) == 0`                                       | `velocities == []`, `accelerations == []`, all per-axis dynamic metrics `None`; `summary[axis]` has `n_total=0`, `n_defined=0`, all metrics `None`. |
| **Single snapshot** | `len(T) == 1`                                       | Same as Empty for dynamic metrics. `summary` reports `n_total=1`, `n_defined ∈ {0, 1}`.                                                            |
| **Undefined axis**  | `axis_series(a)` is all `None`                      | For axis `a`: `drift=None`, `volatility=None`, `path_length=None`, `mean=None`, `std=None`, `n_defined=0`.                                         |
| **Saturated axis**  | `axis_series(a)` is constant, length ≥ 2            | For axis `a`: `drift=0`, `volatility=0`, `path_length=0`, `std=0`, `velocities` are all zero. Theorem LD-1 specialises here.                       |
| **Mosaic-degraded** | `axis_series(a)` has both `None` and defined values | Computation runs over the defined sub-series; `n_defined` reports how many slots survived; metrics may still be `None` if `n_defined < 2`.         |

### LD-3. Rolling-window contract

`rolling_mean(axis, window)` and `rolling_std(axis, window)` use a
**right-aligned (trailing)** window of length `window`. Output
positions `0 .. window - 2` always emit `None` (the window does not
yet fit). For positions `i >= window - 1` the window covers
`series[i - window + 1 : i + 1]`. The window emits a value iff at
least `ceil(window / 2)` of its slots are defined; otherwise it emits
`None`. `rolling_std` further requires at least two defined slots
inside the window (sample standard deviation is undefined for a single
observation).

This contract is locked because alternatives (centred window, full
strict window, expanding window) would each silently change the
meaning of every test that follows. A future cycle may add other
window kinds as additional methods, but it may not change the
semantics of these two.

### LD-4. `volatility` operates on velocities, not values

`volatility(axis)` is the sample standard deviation (`ddof=1`) of the
**defined velocities** along the axis, not of the raw values. The
distinction matters in two places:

- A monotone trajectory has positive `drift` but zero `volatility`
  when the velocity is constant. This separates "moves a lot" (large
  `path_length`) from "moves erratically" (large `volatility`).
- The same trajectory has positive `summary[axis]["std"]`, which
  *does* reflect spread of values. `std` and `volatility` are
  intentionally distinct in `summary`.

### LD-5. Mosaic-dropout is fielty preserved

No primitive fabricates a value when an axis is missing. The
operationalisation is borrowed from Autonometrics: `None` propagates
through differences (`x - None == None`), but it does not abort
aggregations (sums, sample statistics): the aggregator runs over the
defined sub-list and reports `None` only when the sub-list is too
small for the operation to be defined.

---

## Predicted outcomes

The cycle ships a positive verdict iff all four predictions below
hold without deviation.

### PO-1. Saturation theorem holds numerically

For every synthetic saturated trajectory the test suite constructs,
LD-1 holds within tolerance `1e-12`.

### PO-2. Boundary regimes match LD-2

Each of the five regimes named in LD-2 is exercised by at least one
test, and every value emitted matches the table.

### PO-3. CSV ingestion is total

Loading
[`tests/fixtures/autonometrics_v0_8_sample.csv`](../tests/fixtures/autonometrics_v0_8_sample.csv)
(a 15-row reproducible subset of the public
`bugerchip/Autonometrics docs/benchmarks/v0.8.0a0.csv`), grouping by
`(class, params)`, ordering by `seed` and feeding the resulting
3 trajectories of 5 snapshots each through `summary()` produces no
exceptions and yields well-typed output for every group.

### PO-4. Saturation in real data matches the theorem

For the `(PeriodicCycle, period=2)` group of the fixture — a known
saturation case in the Autonometrics zoo — the per-axis summary
reports `volatility = 0`, `drift = 0` and `path_length = 0`
**exactly** for the three axes that are saturated in the source data
(`closure = 1.0` everywhere, `constraint = 0.0` everywhere,
`persistence = 0.0` everywhere). The same group reports
`coherence` as fully undefined (`n_defined = 0`, all metrics `None`).
The `memory` axis, which is *not* saturated for this group, reports
strictly positive `volatility` and `path_length`.

This is a sanity check, not a discovery: the saturation pattern was
already documented for the four-axis cloud in
[`docs/ATLAS_GEOMETRY.md`](https://github.com/bugerchip/Autonometrics/blob/main/docs/ATLAS_GEOMETRY.md)
of Autonometrics. The prediction is that Autodynamics does not
*break* it.

---

## Implementation report

The implementation lives in
[`src/autodynamics/trajectory.py`](../src/autodynamics/trajectory.py)
as methods of `ProfileTrajectory`. The eight public algebra
primitives — `velocities`, `accelerations`, `drift`, `volatility`,
`path_length_per_axis`, `rolling_mean`, `rolling_std`, `summary` —
are written as a small layer over a handful of private helpers
(`_velocities_for`, `_accelerations_for`, `_drift_for`,
`_volatility_for`, `_path_length_for`, `_rolling`). Public methods
that accept an `axis` argument follow a single convention: passing
`None` (the default) returns a dict over all axes configured on the
trajectory; passing a canonical axis name returns the value for that
axis directly.

Tests are split across two files:

- [`tests/test_algebra.py`](../tests/test_algebra.py) — 46 tests
  exercising every primitive against synthetic trajectories
  (constant, monotone, oscillating, mosaic-dropout, single-snapshot,
  empty, with rolling windows of varying widths).
- [`tests/test_diagnostics.py`](../tests/test_diagnostics.py) — the
  pre-registration tests of this document. PO-1 through PO-4 each
  map to at least one explicit test.

The fixture
[`tests/fixtures/autonometrics_v0_8_sample.csv`](../tests/fixtures/autonometrics_v0_8_sample.csv)
is a verbatim subset of the Autonometrics `v0.8.0a0` benchmark.
Origin and reproducibility instructions live in
[`tests/fixtures/README.md`](../tests/fixtures/README.md).

---

## Verdict

The verdict is recorded after the test suite goes green, before the
cycle is merged.

**v0.2.0a0**: positive. PO-1 through PO-4 all pass on the cycle's
test suite (`pytest tests/`). No deviations from this pre-registration
were required.

---

## Deviations from pre-registration

None recorded for `v0.2.0a0`.

---

*End of pre-registration. Future cycles may extend this document with
new locked decisions and predictions; existing entries are preserved
and annotated with their cycle of origin.*

# Coupling diagnostics

**Status**: pre-registration. Locked at the start of the `v0.3.0a0`
cycle, before any of the implementation report below was written.

**Cycle**: `v0.3.0a0` (Granger-causal coupling primitives).

**Predecessor design documents**:
[`docs/TRAJECTORY_DIAGNOSTICS.md`](TRAJECTORY_DIAGNOSTICS.md) (`v0.2.0a0`).
The discipline (locked decisions, named boundary regimes, falsifiable
predicted outcomes) is the same.

---

## Why this document exists

`v0.2.x` shipped a recording substrate plus algebra of trajectories.
Those primitives are *intra-axis*: every method takes one axis at a
time and reports a property of that single time series.

`v0.3.0a0` adds the smallest *cross-axis* primitive: a directed
Granger-causal coupling graph between every pair of admitted axes of
a `ProfileTrajectory`. The graph itself is not a discovery. It is the
standard pairwise Granger test (Granger 1969; Sims 1980;
Lütkepohl 2005) applied uniformly to the axes of the autonomy atlas,
plus four scalar diagnostics — `symmetry_ratio`, `density`,
`max_in_strength`, `max_out_strength` — that summarise the graph.

Because the toolbox composes a stationarity gate, a VAR fit, an F-test
and a dropout policy, it is also easy to misread its output. A caller
who runs `granger_graph` on a trajectory of 60 snapshots and gets four
out of five axes excluded with reason `mosaic_dropout` may not know
whether the trajectory is genuinely degraded, the threshold is too
strict, or the longest contiguous run extracted by the policy is the
wrong sub-series for their question.

This document fixes the **domain of applicability** of every primitive
*before* the implementation, so that future readers can audit the
implementation against a written specification rather than against
tribal knowledge.

---

## What this cycle is *not*

This cycle is deliberately conservative. It registers properties of
the **implementation**, not properties of the systems whose
trajectories the implementation analyses. It does *not*:

- claim that any particular axis Granger-causes any other axis on
  any specific Autonometrics zoo,
- name causal regimes,
- reduce the five-axis atlas to a directed graph of "true" causes,
- predict transitions or attractors from coupling structure.

Those claims, if made at all, will only be added if and when an
explicit pre-registered design document is shipped. Empirical claims
about real data live in their own `docs/<COMPONENT>_VALIDATION.md`
documents (see [`docs/COUPLING_VALIDATION.md`](COUPLING_VALIDATION.md)
for the cycle's validation track against the public Autonometrics
benchmark).

---

## Locked decisions

### LD-1. Pairwise Granger protocol

For two one-dimensional series `x_a` and `x_b` of length `n_a` and
`n_b`, the directional coupling `g(a -> b)` is computed as follows:

1. **Length gate**: if `n_a < n_min` or `n_b < n_min` (default
   `n_min = 50`), return status `too_short`.
2. **Constant gate**: if either series has standard deviation below
   `1e-12`, return status `constant_series`.
3. **Stationarity gate**: apply the Augmented Dickey-Fuller (ADF)
   test (`statsmodels.tsa.stattools.adfuller`, `autolag="AIC"`).
   If the p-value is at or above `0.05`, take a first difference and
   re-test; if still non-stationary, take a second difference. If the
   second-differenced series is still non-stationary, return status
   `non_stationary`.
4. **VAR fit**: stack the (possibly differenced) series into a
   `(n, 2)` array and fit a bivariate VAR with lag selected by AIC up
   to `max_lag` (default `6`). The selected lag is at least `1`.
5. **F-test**: run `var_fit.test_causality(caused=1, causing=0,
   kind="f", signif=0.05)`. The reported F-statistic is `g(a -> b)`.
6. **Finiteness gate**: if the F-statistic is non-finite (degenerate
   residual variance), return status `ftest_failed`.

The convention follows step 5 of the protocol: high `g(a -> b)` means
past lags of `a` significantly improve prediction of `b`. This is the
standard Granger-causality direction (Granger 1969; Lütkepohl 2005,
ch. 7).

### LD-2. Series length threshold

The default minimum effective sample size is `n_min = 50`. This is the
length tested by `granger_coupling`'s length gate (LD-1 step 1) and
also by the post-differencing length check (LD-1 step 4 implicitly:
after one or two diffs, the residual length must still be at least
`n_min`).

The threshold is a deliberate trade-off. It is large enough to give
a bivariate VAR with `max_lag = 6` (LD-3) at least
`50 - 2 * 6 - 1 = 37` residual degrees of freedom — comfortably above
the breaking point of the F-test — but small enough that an autonomy
trajectory of fewer than 50 snapshots is honestly flagged as
under-sampled rather than silently fitted.

Callers may override `n_min` to match a specific use case. The
diagnostics in this document refer to the default.

### LD-3. Maximum lag

The default `max_lag = 6` follows the convention of low-order VAR
fitting on observational time series of moderate length (Lütkepohl
2005, §4.3). The actual lag is selected by AIC inside `[1, max_lag]`.

If AIC selects `0` (no lags), the implementation forces `lag = 1` so
the F-test has at least one lagged regressor to test against.

### LD-4. Mosaic-dropout policy

Following Autonometrics' fielty principle, no primitive fabricates a
value when an axis is missing. For a single axis with `None` (or
`NaN`) entries, the admission policy is:

1. **Coverage gate**: if the fraction of defined values is below
   `mosaic_threshold` (default `0.8`), the axis is excluded with
   reason `mosaic_dropout`.
2. **Longest contiguous run extraction**: among defined-value runs
   inside the series, the longest one is selected (ties broken in
   favour of the earliest start).
3. **Run length gate**: if the selected run has fewer than `n_min`
   values, the axis is excluded with reason
   `too_short_after_dropout`.
4. **Saturation gate**: if the run has standard deviation below
   `saturation_tol` (default `1e-12`), the axis is excluded with
   reason `saturated_axis`.

`NaN` is treated identically to `None`: both are coerced to `None`
during ingestion, then handled by the same policy.

The longest-contiguous-run extraction is critical: silent stitching
of disjoint runs would falsify the temporal structure VAR estimation
depends on. Splicing introduces an artificial discontinuity that VAR
will model as a spurious shock; pre-cycle simulations rejected that
alternative.

### LD-5. Pair admission rules

A pair `(a, b)` is admitted iff both axes survive LD-4. For every
ordered admitted pair (with `a != b`), the protocol of LD-1 runs.
Pairs whose F-statistic could not be computed are recorded in
`null_pairs` and excluded from aggregates (LD-7).

### LD-6. Boundary regimes (named)

| Regime                         | Definition                                                                  | Expected behaviour                                                                                                                  |
|--------------------------------|------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| **Empty mapping/trajectory**    | No axis present.                                                             | `axes_used == ()`, `len(edges) == 0`, `null_pairs == ()`, `n_obs_min == 0`.                                                          |
| **Single admitted axis**        | Exactly one axis survives LD-4.                                              | `axes_used` has one element; `len(edges) == 0`. No directed pair to test.                                                            |
| **All-saturated**               | Every axis has zero defined-value variance.                                  | Every axis recorded in `excluded_axes` with reason `saturated_axis`. `n_obs_min == 0`.                                              |
| **Mosaic-degraded**             | Coverage below threshold on at least one axis.                               | Degraded axes recorded in `excluded_axes` with reason `mosaic_dropout`. Surviving axes admitted normally.                            |
| **Random-walk pair**            | Both series unit-root non-stationary; first-differenced series stationary.  | LD-1 step 3 succeeds at `n_diff = 1`; status `ok`; `n_diff_a == 1` and `n_diff_b == 1`.                                              |
| **Stubborn non-stationary**     | Series remains non-stationary after two differences.                         | Status `non_stationary`, `f_stat is None`.                                                                                           |
| **Constant series**             | Either series has zero variance, before or after differencing.               | Status `constant_series`, `f_stat is None`.                                                                                          |

### LD-7. Diagnostics aggregate semantics

For a `CausalCouplingGraph` `G`:

- **`symmetry_ratio(G)`** is the arithmetic mean of
  `min(g_ab, g_ba) / max(g_ab, g_ba)` over **unordered pairs**
  `{a, b}` for which both `g_ab` and `g_ba` are finite and at least
  one is positive. Returns `None` if no such pair exists. Range:
  `[0, 1]`. A value near `1.0` indicates approximately symmetric
  coupling; a value near `0.0` indicates strong asymmetry.

- **`density(G, tau=tau, alpha=alpha)`** is the fraction of edges
  `(a, b)` whose F-stat exceeds the threshold. If `tau` is provided,
  it is the threshold; otherwise, the threshold is the per-edge F
  critical value at level `alpha` for that edge's selected lag and
  effective sample size. Edges whose F-stat is `None`, or whose
  per-edge critical value is undefined (`df2 <= 0`), are excluded
  from both numerator and denominator. Returns `None` if no edge
  survives.

- **`max_in_strength(G, axis)`** is the maximum F-statistic over the
  edges `(a, axis)` with `a != axis` and `f_stat` finite. Returns
  `None` if `axis` has no admitted incoming edge with finite F-stat.

- **`max_out_strength(G, axis)`** is the maximum F-statistic over the
  edges `(axis, b)` with `b != axis` and `f_stat` finite. Returns
  `None` if `axis` has no admitted outgoing edge with finite F-stat.

All four diagnostics return `None` (not zero, not exception) when no
admitted edge has a finite F-statistic. This mirrors the
`mosaic-dropout` semantics of `ProfileTrajectory` algebra primitives.

---

## Predicted outcomes

The cycle ships a positive verdict iff all four predictions below
hold without deviation.

### PO-1. Determinism

For any fixed `(seed, source, max_lag, n_min, saturation_tol,
mosaic_threshold)`, calling `granger_graph(...)` twice produces
identical F-statistics on every admitted edge.

**Verification threshold**: bit-equality of `f_stat` per edge.

### PO-2. Causality direction is recovered on synthetic AR pairs

Across at least six independently seeded synthetic causal pairs
`(a, b)` constructed as
`b[t] = phi * b[t-1] + k * a[t-1] + eps_b[t]`
with `phi = 0.5`, `k = 0.8`, `n = 200` and `eps ~ N(0, 1)`:

- For every seed, both `g(a -> b)` and `g(b -> a)` complete with
  status `ok`.
- In a strict majority of seeds, `g(a -> b) > g(b -> a)`.

**Verification threshold**: at least four of six seeds show
`g(a -> b) > g(b -> a)`.

### PO-3. Independent AR pairs do not produce systematic significance

Across at least six independently seeded pairs of independent AR(1)
processes (`phi = 0.5`, `n = 200`), the rate of pairs reporting a
p-value below `0.05` is bounded.

**Verification threshold**: at most two of six pairs return
`p_value < 0.05`. (Strictly, a uniform-under-null test would expect
five percent of pairs to fall below 0.05; the bound at one third of
six is loose to absorb finite-sample noise.)

### PO-4. Mosaic-dropout fielty preserved

For a `ProfileTrajectory` of length 200 in which one axis has a
contiguous block of 20 `None` values (rest defined) and another axis
is fully defined, with `mosaic_threshold = 0.5`:

- The axis with the gap is admitted (longest contiguous run length
  130, above `n_min = 50`).
- Both axes appear in `axes_used`; neither in `excluded_axes`.

**Verification threshold**: explicit assertion in the test suite.

---

## Implementation report

The implementation lives in
[`src/autodynamics/coupling/`](../src/autodynamics/coupling/) as four
modules:

- [`granger.py`](../src/autodynamics/coupling/granger.py) — pairwise
  primitive `granger_coupling` plus its result dataclass
  `CausalCouplingResult`. Implements LD-1, LD-2, LD-3.
- [`graph.py`](../src/autodynamics/coupling/graph.py) — graph-level
  entry point `granger_graph`, the `CausalCouplingGraph` dataclass,
  and the dispatch between `ProfileTrajectory` and mapping inputs.
  Implements LD-4, LD-5, LD-6.
- [`metrics.py`](../src/autodynamics/coupling/metrics.py) — the four
  scalar diagnostics. Implements LD-7.
- [`__init__.py`](../src/autodynamics/coupling/__init__.py) — public
  API surface; re-exported at the top level of `autodynamics`.

Tests are split across two files:

- [`tests/test_coupling_smoke.py`](../tests/test_coupling_smoke.py) —
  11 smoke tests covering imports, return types, basic synthetic
  cases, and `None` propagation.
- [`tests/test_coupling.py`](../tests/test_coupling.py) — 41 tests
  exercising the locked decisions and predicted outcomes, organised
  by section: pairwise invariants, causality direction, graph
  dispatch and admission, helpers, dataclass invariants, metrics, and
  determinism. PO-1 through PO-4 each map to at least one explicit
  test.

---

## Verdict

The verdict is recorded after the test suite goes green, before the
cycle is merged.

**v0.3.0a0**: positive. PO-1 through PO-4 all pass on the cycle's
test suite (`pytest tests/`). No deviations from this pre-registration
were required.

---

## Deviations from pre-registration

None recorded for `v0.3.0a0`.

---

## References

- Granger, C. W. J. (1969). "Investigating Causal Relations by
  Econometric Models and Cross-spectral Methods." *Econometrica*
  37 (3): 424-438.
- Sims, C. A. (1980). "Macroeconomics and Reality." *Econometrica*
  48 (1): 1-48.
- Lütkepohl, H. (2005). *New Introduction to Multiple Time Series
  Analysis*. Springer.

---

*End of pre-registration. Future cycles may extend this document with
new locked decisions and predictions; existing entries are preserved
and annotated with their cycle of origin.*

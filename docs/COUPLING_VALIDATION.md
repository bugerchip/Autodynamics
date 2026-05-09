# Coupling validation — public experiment v0.3.0a0

**Status**: pre-registration. Locked at the time this document was
committed, before any computation ran against the source data. The
git history of the originating branch records the exact moment.

**Cycle context**: this experiment lives on the **parallel public
validation track** registered in the `v0.2.0a0` cycle and continued
in `v0.2.1a0`. It is the second falsifiable hypothesis the
public-validation track ships, after
[`docs/TURBULENCE_RANKING.md`](TURBULENCE_RANKING.md). It tests the
`v0.3.0a0` coupling primitives shipped in
[`docs/COUPLING_DIAGNOSTICS.md`](COUPLING_DIAGNOSTICS.md) against
real, public data using only those primitives plus the pre-existing
`ProfileTrajectory` substrate.

**Companion documents**:

- [`docs/COUPLING_DIAGNOSTICS.md`](COUPLING_DIAGNOSTICS.md) — locked
  decisions for the coupling primitives this experiment relies on.
- [`docs/TRAJECTORY_DIAGNOSTICS.md`](TRAJECTORY_DIAGNOSTICS.md) —
  locked decisions for the underlying trajectory algebra.
- [`docs/TURBULENCE_RANKING.md`](TURBULENCE_RANKING.md) — sister
  validation experiment on the same zoo.

---

## What this experiment is — and is not

**It is** a pre-registered, falsifiable hypothesis about whether
`granger_graph` produces non-trivial output on the publicly
available
[`bugerchip/Autonometrics`](https://github.com/bugerchip/Autonometrics)
`v0.8.0a0` benchmark, using only the `v0.3.0a0` coupling primitives.

**It is not**:

- A claim about temporal causality. The Autonometrics CSVs do not
  record system state through time. Each row is one
  independently-seeded system from the same regime. The
  pseudo-trajectory built per group `(class, params)` is sorted by
  `seed`, not by any clock. Any "Granger causality" detected in this
  setting is a property of how the cross-seed dispersion of one axis
  predicts the cross-seed dispersion of another, **not** a property
  of how one axis temporally drives another inside a single system.
- A claim about LLMs, agents, or any commercial use case.
- A benchmark against another library.
- A calibration against private data.

The hypothesis is therefore narrow on purpose: if it confirms, it
shows that the coupling primitives produce mechanically meaningful
output on the kind of data the public zoo provides — that is,
trajectory-like sequences of profiles, even when those sequences are
ordinal (seed) rather than temporal (clock). If it rejects, it shows
that the zoo as currently shaped is too coarse-grained for the
default Granger configuration to extract usable structure.

---

## Locked decisions

### LD-1. Source dataset

Single source: `bugerchip/Autonometrics docs/benchmarks/v0.8.0a0.csv`
(public, n = 645 rows, 31 groups, 5 system classes, 5 canonical
axes). No earlier release is consulted (constraint and persistence
columns are absent in `v0.5.x`–`v0.6.x`; coherence is absent before
`v0.8.0a0`). No private data is consulted.

### LD-2. Trajectory construction per group

For each group `(class, params)` present in the source, rows are
sorted by integer `seed` and a `ProfileTrajectory` is built with the
canonical axis names. No re-ordering, no resampling, no
normalisation. Trajectory length equals the number of seeds in the
group (15–30 in this dataset).

### LD-3. Coupling configuration

Because the per-group trajectory length (15–30) is below the
`n_min = 50` default of the coupling primitives (LD-2 of
`docs/COUPLING_DIAGNOSTICS.md`), this validation deliberately runs
at relaxed parameters:

- `n_min = 10` (allows the zoo's shortest groups to participate),
- `max_lag = 2` (sized to leave at least
  `15 - 2 * 2 - 1 = 10` residual degrees of freedom for the F-test
  on the smallest groups),
- `mosaic_threshold = 0.5` (axes with up to half their values
  missing are admitted; this matches the `coherence` axis pattern in
  the zoo, where many groups report `coherence` only on a subset of
  seeds),
- `saturation_tol = 1e-12` (default).

The relaxation is the experiment's most consequential design
decision. The intent is to give the primitive the most charitable
configuration the zoo allows. If the experiment rejects under these
parameters, the rejection is even stronger: stricter parameters
would only make the picture worse.

### LD-4. Per-group output

Each group produces one `CausalCouplingGraph`. The recorded outputs
per group are:

- the number of admitted axes (`len(graph.axes_used)`),
- the number of directed edges produced
  (`len(graph.edges)`),
- the number of edges with finite `f_stat` (admitted minus
  `null_pairs`),
- the number of edges with `p_value < 0.05` among edges with
  finite `f_stat`,
- the value of `symmetry_ratio(graph)` (or `None`),
- the value of `density(graph)` (or `None`),
- the per-axis exclusion reasons in `graph.excluded_axes`.

### LD-5. Verification rule

Hypothesis is **confirmed** iff all three Predicted Outcomes below
hold; **rejected** otherwise. The thresholds are intentionally
loose: this is the first time the coupling primitives meet real
public data, and the test is whether the primitives produce a
defensible foothold, not whether they reveal a deep structural law.

### LD-6. Reporting discipline

Every numeric output is written to
`docs/benchmarks/coupling_v0.3.0a0.csv` and the full stdout to
`docs/benchmarks/coupling_v0.3.0a0.log.txt`. The experiment is
reproducible from `examples/coupling_validation.py`. The script
accepts `--autonometrics-root` to locate the source CSV; the default
is `../Autonometrics` relative to this repository.

The Verdict section below is filled in **after** the script runs.
LD-1 through LD-5 are not modified after seeing the results. Any
unavoidable deviation is recorded under "Deviations" and named
explicitly.

---

## Predicted outcomes

- **PO-1.** The script runs to completion on the source CSV without
  exceptions.
- **PO-2.** At least **50%** of the 31 groups produce a graph with
  at least two admitted axes (i.e. at least one orderable pair to
  test).
- **PO-3.** Across all groups, at least **30%** of the directed
  edges admitted (`len(graph.edges)` summed over groups) carry a
  finite `f_stat` (i.e. the VAR + F-test pipeline survives the
  zoo's short-trajectory regime more often than not on a relative
  basis).

PO-1 is an infrastructure precondition. PO-2 is a structural test
about whether the zoo provides sufficient axis diversity for
coupling to be even nominally measurable. PO-3 is the actual claim
about the primitive's robustness on real, short trajectories.

Honest prior probability of confirming all three:

- PO-1: > 95% (defensive coding throughout the module).
- PO-2: ≈ 60% (the zoo is known to saturate `closure`,
  `constraint`, `persistence` at extremes for clean classes; only
  `KauffmanNetwork` is reliably non-saturated).
- PO-3: ≈ 40% (15–30 sample VAR fits with `max_lag = 2` are right
  at the edge of statistical defensibility).

The combined probability of confirming the hypothesis is therefore
around **20–30%**. **A REJECTED verdict is the more probable
outcome.**

---

## Implementation report

First run executed against
`Autonometrics/docs/benchmarks/v0.8.0a0.csv` (n = 645 rows, 31 groups,
5 system classes, 5 canonical axes). The script materialised one
`ProfileTrajectory` per group via `CSVTrajectoryAdapter`, then ran
`granger_graph` against each group with the LD-3 configuration
(`n_min=10`, `max_lag=2`, `mosaic_threshold=0.5`,
`saturation_tol=1e-12`).

### Per-class summary of admission

| Class             | groups | groups with ≥ 2 admitted axes |
|-------------------|--------|-------------------------------|
| `ECASystem`       | 5      | 2 (`rule=30`, `rule=110`)      |
| `KauffmanNetwork` | 5      | 0                              |
| `PeriodicCycle`   | 3      | 0                              |
| `PromisedCycle`   | 16     | 12                             |
| `SimpleAutomaton` | 2      | 1 (`external`)                 |
| **Total**         | **31** | **15**                         |

### Per-class summary of edges

Counts are summed across the groups of each class.

| Class             | edges admitted | edges with finite `f_stat` | edges with `p < 0.05` |
|-------------------|----------------|----------------------------|------------------------|
| `ECASystem`       | 4              | 4                          | 1                      |
| `KauffmanNetwork` | 0              | 0                          | 0                      |
| `PeriodicCycle`   | 0              | 0                          | 0                      |
| `PromisedCycle`   | 24             | 22                         | 2                      |
| `SimpleAutomaton` | 2              | 2                          | 0                      |
| **Total**         | **30**         | **28**                     | **3**                  |

### Aggregate evaluation

| Predicted outcome                                                     | Threshold | Observed         | Outcome |
|------------------------------------------------------------------------|-----------|------------------|---------|
| **PO-1.** script runs to completion                                    | —         | runs cleanly      | **PASS** |
| **PO-2.** ≥ 50 % of groups with ≥ 2 admitted axes                       | 0.50      | 15 / 31 = 0.4839  | **FAIL** |
| **PO-3.** ≥ 30 % of admitted edges with finite `f_stat`                 | 0.30      | 28 / 30 = 0.9333  | **PASS** |

Full per-group output is preserved in
`docs/benchmarks/coupling_v0.3.0a0.csv` and the full stdout in
`docs/benchmarks/coupling_v0.3.0a0.log.txt`.

---

## Verdict

**Hypothesis: REJECTED.**

PO-1 and PO-3 hold; PO-2 falls short by **a single group** (15 of 31
required to clear the 50 % threshold; 16 would have confirmed). The
rejection is honest and expected — the pre-registration explicitly
flagged PO-2 as the weakest leg with prior probability ≈ 60 % — and
three findings stand out, treated as **observations to keep in
mind**, not as edits to LD-1 through LD-5:

1. **The pipeline survives the regime; it just runs out of axes to
   couple.** Where two axes are admitted, 28 of 30 directed edges
   produce a finite F-statistic (93 %). The VAR fit + F-test
   pipeline is robust at `max_lag = 2` and trajectory length 15–30,
   contrary to the conservative prior. PO-3 confirms.

2. **Significance is consistent with no real coupling on this zoo.**
   Among the 28 finite-F edges, only 3 (10.7 %) clear `p < 0.05`.
   Under the null hypothesis of no coupling, the expected
   false-positive rate at `alpha = 0.05` is 5 %. The observed rate
   (10.7 %) is mildly above the nominal level but does not point to
   any concentrated direction of coupling: the three significant
   edges are spread across `ECASystem rule=30`, `PromisedCycle
   period=4,alphabet=4,p_noise=0.10` and `PromisedCycle
   period=4,alphabet=4,p_noise=0.30`, with no shared source or
   sink. This is consistent with the "siblings of the same regime"
   reading from `docs/TURBULENCE_RANKING.md`: cross-seed dispersion
   ordering does not encode temporal causality, so detecting sparse
   spurious coupling at roughly the nominal rate is exactly the
   expected null behaviour.

3. **Saturation is the real bottleneck for PO-2.** All 5
   `KauffmanNetwork` groups, all 3 `PeriodicCycle` groups and 4 of 5
   `ECASystem` groups admit fewer than 2 axes. The reason is the
   already-documented saturation pattern of the
   `Autonometrics v0.8.0a0` zoo: `closure`, `constraint` and
   `persistence` collapse to constant values for clean classes, and
   `coherence` is missing for everyone except `PromisedCycle`. With
   only one or zero non-saturated axes, no orderable pair survives
   LD-4. This is a property of the **input** zoo, not of the
   coupling primitive.

These findings stand on their own as observations about the
Autonometrics `v0.8.0a0` zoo: the coupling primitive is robust on
the trajectories the zoo allows it to see, but the zoo's saturation
pattern keeps half of its groups from reaching the two-axis
threshold needed to express any coupling at all. They do not in
themselves motivate a successor cycle; that decision is left for
whenever a concrete pre-registered design document is ready to make
use of them.

---

## Deviations from pre-registration

None. LD-1 through LD-6 were enforced exactly as committed.
`_PO2_MIN_GROUPS_WITH_TWO_AXES_FRACTION` and
`_PO3_MIN_FINITE_EDGES_FRACTION` in `examples/coupling_validation.py`
were not modified between the pre-registration commit and the run.

---

## References

- Granger, C. W. J. (1969). "Investigating Causal Relations by
  Econometric Models and Cross-spectral Methods." *Econometrica*
  37 (3): 424-438.
- Sims, C. A. (1980). "Macroeconomics and Reality." *Econometrica*
  48 (1): 1-48.
- Lütkepohl, H. (2005). *New Introduction to Multiple Time Series
  Analysis*. Springer.

# Turbulence ranking — public validation experiment v0.2.1a0

**Status**: pre-registration. Locked at the time this document was committed,
before any computation ran against the source data. The git history of the
originating branch records the exact moment.

**Cycle context**: this experiment lives on the **parallel public-validation
track** registered in the `v0.2.0a0` cycle. It is not part of the v0.2.x core
API cycle (those were closed by `v0.2.0a0`). It is the first attempt at a
falsifiable hypothesis about real, public data using only the algebra
primitives shipped in `v0.2.0a0`.

**Companion documents**: [`docs/TRAJECTORY_DIAGNOSTICS.md`](TRAJECTORY_DIAGNOSTICS.md)
locks the algebra primitives this experiment relies on.

---

## What this experiment is — and is not

**It is** a pre-registered, falsifiable ranking hypothesis over the
**cross-seed dispersion** of the publicly available
[`bugerchip/Autonometrics`](https://github.com/bugerchip/Autonometrics)
`v0.8.0a0` benchmark, using only the `v0.2.0a0` algebra primitives.

**It is not**:

- A dynamic hypothesis about temporal evolution. The Autonometrics
  CSVs do not record system state through time. Each row is one
  independently-seeded system from the same regime. What the
  experiment measures is dispersion across **siblings of the same
  regime**, not movement over time. The pseudo-trajectory built per
  group `(class, params)` is sorted by `seed`, not by any clock.
- A claim about LLMs, agents, or any commercial use case.
- A benchmark against another library.
- Calibration against private data.

The hypothesis is therefore narrow on purpose: if it confirms, it
shows that the volatility primitive of `ProfileTrajectory`, when fed
cross-seed siblings, recovers an intuitive turbulence ordering of
the zoo. If it rejects, it shows that this ordering is not what the
primitive captures, and helps direct the v0.3.x cycle.

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
sorted by integer `seed` and a `ProfileTrajectory` is built with
the canonical axis names. No re-ordering, no resampling, no
normalisation. Trajectory length equals the number of seeds in the
group (15–30 in this dataset).

### LD-3. Aggregation rule

For each `(class, axis)` pair, the **per-class volatility** is the
arithmetic mean of `ProfileTrajectory.volatility(axis)` over every
group of that class whose trajectory has **at least 5 defined values
on the axis**. Groups below that gate are dropped from the per-class
average. Classes with zero qualifying groups produce `None` for the
affected axis.

The minimum of 5 is fixed at this point and not tuned: it is the
smallest sample for which a sample standard deviation is structurally
informative without being dominated by individual data points.

### LD-4. Pre-registered ranking

This ranking is the prediction. **It is fixed at this point in the
document and will not be changed**, regardless of what the experiment
returns. The git commit that introduces this document is the locking
event.

Ranking by ascending cross-seed volatility (least turbulent first):

| Rank | Class             | Reasoning                                                                                                                                                        |
|------|-------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1    | `PeriodicCycle`   | Periodic by construction. Dynamics fully specified by the period; seed only shifts initial phase. Minimal cross-seed variation expected.                          |
| 2    | `SimpleAutomaton` | Small finite-state alphabet, deterministic transitions. Variation comes only from initial conditions; structurally low.                                          |
| 3    | `ECASystem`       | Five rules sampled (30, 90, 110, 184, 250) span Wolfram classes I–IV. Mean over rules sits in the middle of the range.                                            |
| 4    | `PromisedCycle`   | Has an explicit `p_noise` parameter injected by design. Multiple `p_noise` levels in the dataset push the mean upward.                                            |
| 5    | `KauffmanNetwork` | Random Boolean networks with non-trivial coupling. High coupling values are known to produce chaotic regimes (Kauffman 1969); spread across coupling values lifts the mean. |

### LD-5. Verification rule

Per-axis test: for each axis with **at least 3 classes** producing a
non-`None` aggregate volatility, the observed ordering of those
classes by volatility is compared against the pre-registered ranking
restricted to those classes. The metric is the **Spearman rank
correlation** ρ between observed and pre-registered orderings.

- Per-axis pass: ρ ≥ 0.7 (Cohen 1988 convention for "strong"
  correlation).
- Per-axis fail: ρ < 0.7 or undefined (fewer than 3 classes
  available, or zero variance in either ranking).

Hypothesis confirmation: pass in **at least 3 of the 4 evaluable
axes** (`closure`, `memory`, `constraint`, `persistence`).
`coherence` is reported only; the source has coherence values for
`PromisedCycle` only, so a class ranking cannot be computed for it.

Hypothesis rejection: fewer than 3 of 4 evaluable axes pass.

### LD-6. Reporting discipline

Every numeric output is written to
`docs/benchmarks/turbulence_ranking_v0.2.1a0.csv` and the full
stdout to `docs/benchmarks/turbulence_ranking_v0.2.1a0.log.txt`.
The experiment is reproducible from
`examples/turbulence_ranking.py`. The script accepts
`--autonometrics-root` to locate the source CSV; the default is
`../Autonometrics` relative to this repository.

The Verdict section below is filled in **after** the script runs.
LD-4 and LD-5 are not modified after seeing the results. Any
unavoidable deviation is recorded under "Deviations" and named
explicitly.

---

## Predicted outcomes

- **PO-1.** The script runs to completion on the source CSV without
  exceptions.
- **PO-2.** Each evaluable axis (closure, memory, constraint,
  persistence) yields aggregates for at least 3 of 5 classes.
- **PO-3.** The hypothesis (LD-4 ranking, evaluated per LD-5) is
  confirmed.

PO-1 and PO-2 are infrastructure preconditions. PO-3 is the actual
hypothesis. Honest prior probability of PO-3 confirming: 50–60 %.
The ranking is plausible but not obvious; the most likely points of
swap are `ECASystem` ↔ `PromisedCycle` (depending on `p_noise`
distribution) and `SimpleAutomaton` ↔ `ECASystem` (depending on the
sampled rules).

---

## Implementation report

First run executed against
`Autonometrics/docs/benchmarks/v0.8.0a0.csv` (n = 645 rows, 31 groups,
5 system classes, 5 canonical axes). The script materialised 31
`ProfileTrajectory` instances via `CSVTrajectoryAdapter` and a parallel
group-keyed view via `BatchTrajectoryAdapter` for redundancy. Both
preconditions PO-1 (script runs to completion) and PO-2 (every
evaluable axis aggregates ≥ 3 classes) hold:

| Axis        | Classes with aggregate volatility |
|-------------|-----------------------------------|
| closure     | 5 of 5                            |
| memory      | 5 of 5                            |
| constraint  | 4 of 5 (PromisedCycle absent)     |
| persistence | 5 of 5                            |
| coherence   | 1 of 5 (report-only)              |

Per-class average volatility (mean over qualifying groups), as written
to `docs/benchmarks/turbulence_ranking_v0.2.1a0.csv`:

| Class             | closure  | memory   | constraint | persistence | coherence |
|-------------------|----------|----------|------------|-------------|-----------|
| `PeriodicCycle`   | 0.000000 | 0.005143 | 0.000000   | 0.000000    | n/a       |
| `SimpleAutomaton` | 0.003010 | 0.035143 | 0.000000   | 0.000000    | n/a       |
| `ECASystem`       | 0.000000 | 0.041890 | 0.000000   | 0.069508    | n/a       |
| `PromisedCycle`   | 0.006170 | 0.000000 | n/a        | 0.000000    | 0.010612  |
| `KauffmanNetwork` | 0.601363 | 0.434201 | 0.238476   | 0.619198    | n/a       |

Per-axis Spearman ρ between observed ranking and the pre-registered
ranking restricted to the classes present:

| Axis        | n_classes | ρ      | Outcome      |
|-------------|-----------|--------|--------------|
| closure     | 5         | 0.8208 | **PASS**     |
| memory      | 5         | 0.4000 | FAIL         |
| constraint  | 4         | 0.8783 | **PASS**     |
| persistence | 5         | 0.6708 | FAIL         |
| coherence   | 1         | n/a    | report-only  |

Full stdout is preserved verbatim in
`docs/benchmarks/turbulence_ranking_v0.2.1a0.log.txt`.

---

## Verdict

**Hypothesis: REJECTED.**

Evaluable axes that passed (LD-5): 2 of 4 (`closure`, `constraint`).
Required to confirm: 3 of 4. Threshold not met.

The rejection is informative rather than catastrophic, and it is
explicitly the kind of outcome the pre-registration was designed to
capture honestly. Two distinct findings stand out, both treated as
**hypotheses for future cycles**, not as edits to LD-4:

1. **Closure and constraint behave as predicted; memory and
   persistence do not.** The two passing axes are the ones whose
   measurement in Autonometrics is closest to a structural binary
   diagnostic: what fraction of states are reachable from oneself
   (closure) and how much of the future is ruled out by the present
   (constraint). On these axes the cross-seed dispersion ordering
   matches the pre-registered turbulence intuition almost exactly.
   On `memory` and `persistence` it does not: `PromisedCycle`, in
   particular, lands at volatility 0.0 on both, far below where the
   intuition placed it. The cleanest reading is that these two axes
   are saturating to floor or ceiling for `PromisedCycle` regardless
   of `p_noise`, which compresses the cross-seed standard deviation
   to zero. This is a measurement-saturation effect inherited from
   the `v0.8.0a0` Autonometrics zoo, not a property of the
   `ProfileTrajectory` algebra.

2. **Cross-seed dispersion is not the same construct as turbulence
   in the intuitive sense.** Two systems can be equally "boring"
   across siblings (every seed lands on the same fixed point) while
   being completely different in their dynamics through time. The
   experiment confirms that `volatility(axis)` over a seed-sorted
   pseudo-trajectory measures **regime-level concentration**, not
   trajectory turbulence. This distinction was already noted in the
   "What this experiment is — and is not" preamble; the rejection
   sharpens it: cross-seed concentration is a real and useful signal
   on `closure` and `constraint`, but it cannot stand in for
   temporal turbulence on `memory` and `persistence`.

Both findings are direct input for the v0.3.x cycle (Coupling Graph
Γ). The Γ programme already presupposes that not all five axes
co-vary the same way; this experiment provides the first piece of
public evidence that the asymmetry has a measurable, repeatable
structure.

---

## Deviations from pre-registration

None. LD-1 through LD-6 were enforced exactly as committed in
`9a3d88c`. The ranking constants in `examples/turbulence_ranking.py`
were not modified between the pre-registration commit and the run.

# Envelope validation — public experiment v0.4.0a0

**Status**: pre-registration. Locked at the time this document was
committed, before any computation ran against the source data. The
git history of the originating branch records the exact moment.

**Cycle context**: this experiment lives on the **parallel public
validation track** registered in the `v0.2.0a0` cycle and continued
in `v0.2.1a0` and `v0.3.0a0`. It is the third falsifiable
hypothesis the public-validation track ships, after
[`docs/TURBULENCE_RANKING.md`](TURBULENCE_RANKING.md) and
[`docs/COUPLING_VALIDATION.md`](COUPLING_VALIDATION.md). It tests
the `v0.4.0a0` envelope primitives shipped in
[`docs/ENVELOPE_DIAGNOSTICS.md`](ENVELOPE_DIAGNOSTICS.md) against
real, public data using only those primitives plus the pre-existing
`ProfileTrajectory` substrate.

**Companion documents**:

- [`docs/ENVELOPE_DIAGNOSTICS.md`](ENVELOPE_DIAGNOSTICS.md) —
  locked decisions for the envelope primitives this experiment
  relies on.
- [`docs/TRAJECTORY_DIAGNOSTICS.md`](TRAJECTORY_DIAGNOSTICS.md) —
  locked decisions for the underlying trajectory algebra.
- [`docs/TURBULENCE_RANKING.md`](TURBULENCE_RANKING.md),
  [`docs/COUPLING_VALIDATION.md`](COUPLING_VALIDATION.md) — sister
  validation experiments on the same zoo.

---

## What this experiment is — and is not

**It is** a pre-registered, falsifiable hypothesis about whether
:meth:`Envelope.from_trajectory` learns admissible regions that
generalise within a regime — that is, whether an envelope learned
from a subset of a group's seeds usefully bounds the remaining
seeds of the same group.

**It is not**:

- A claim about temporal causality. Each row is one independently
  seeded system from the same regime; the train/test split is over
  seeds, not over time.
- A claim that the envelopes generalise *across* regimes. The
  experiment deliberately stays inside one group at a time.
- A claim about LLMs, agents, or any commercial use case.
- A benchmark against another library.
- A calibration target for any application.

The hypothesis is therefore narrow on purpose: if it confirms, it
shows that the envelope primitive learned from a subset of a
regime's seeds usefully covers the other seeds of the same regime.
If it rejects, it shows that cross-seed dispersion inside a regime
is wider than a 2-sigma band can cover, given the zoo's structure.

---

## Locked decisions

### LD-1. Source dataset

Single source: `bugerchip/Autonometrics docs/benchmarks/v0.8.0a0.csv`
(public, n = 645 rows, 31 groups, 5 system classes, 5 canonical
axes). No earlier release is consulted. No private data is
consulted.

### LD-2. Train / test split per group

For each group `(class, params)`, the rows are sorted by integer
``seed`` ascending. The first ``ceil(0.7 * n_seeds)`` rows form
the **train** subset; the remaining rows form the **test** subset.
Groups whose test subset is empty (``n_seeds == 1``) are excluded
from the experiment and reported separately.

The 70 / 30 split is fixed at this point and not tuned. It is a
standard out-of-sample split that leaves enough train data for the
envelope to be defined on at least one axis (the saturated regimes
in the zoo concentrate on the 4-5 most populated groups, which all
have ``n_seeds >= 15``).

### LD-3. Envelope construction

For each group, the envelope is

```
Envelope.from_trajectory(
    train_trajectory,
    width_multiplier=2.0,
    axes=None,                  # all configured axes
)
```

with the cycle defaults documented in
[`docs/ENVELOPE_DIAGNOSTICS.md`](ENVELOPE_DIAGNOSTICS.md). Axes
that the train subset cannot bound (``n_defined < 2`` or all
profiles ``None``) are silently dropped (LD-6 of the diagnostics).

### LD-4. Per-group output

Each group produces:

- ``n_train``, ``n_test``: integers,
- ``axes_admitted``: tuple of bounded axes in the envelope,
- ``test_inside``, ``test_outside``, ``test_undefined``: integer
  counts of test-set verdicts.

A group is reported even when ``axes_admitted`` is empty: in that
case every test profile is ``INSIDE`` (per LD-3 step 3 of the
diagnostics) and the envelope is uninformative. We label such
groups ``trivial`` in the report.

### LD-5. Verification rule

Hypothesis is **confirmed** iff all three Predicted Outcomes below
hold. Each PO is computed over **non-trivial** groups only — groups
whose envelope admits at least one axis. Trivial groups are
reported but excluded from the aggregation, on the grounds that
they trivially "pass" without testing anything.

### LD-6. Reporting discipline

Every numeric output is written to
`docs/benchmarks/envelope_v0.4.0a0.csv` and the full stdout to
`docs/benchmarks/envelope_v0.4.0a0.log.txt`. The experiment is
reproducible from `examples/envelope_validation.py`. The script
accepts `--autonometrics-root` to locate the source CSV; the
default is `../Autonometrics` relative to this repository.

The Verdict section below is filled in **after** the script runs.
LD-1 through LD-5 are not modified after seeing the results. Any
unavoidable deviation is recorded under "Deviations" and named
explicitly.

---

## Predicted outcomes

- **PO-1.** The script runs to completion on the source CSV without
  exceptions.
- **PO-2.** Across non-trivial groups, the aggregated rate of test
  profiles classified as **not OUTSIDE** (i.e. ``INSIDE`` or
  ``UNDEFINED``) is at least **70%**. This is the round-trip
  test: an envelope learned from the first 70% of a regime's
  seeds should not flag as ``OUTSIDE`` more than 30% of the
  remaining seeds, on average.
- **PO-3.** Across non-trivial groups, the aggregated rate of test
  profiles classified as ``INSIDE`` (excluding ``UNDEFINED`` from
  the numerator) is at least **40%**. This is the "informative
  coverage" test: at least four-tenths of test profiles must
  produce a positive containment, not just "absence of
  violation".

PO-1 is an infrastructure precondition. PO-2 is the soft
generalisation test (counts ``UNDEFINED`` as benign). PO-3 is the
strict generalisation test (only counts positive ``INSIDE``).

Honest prior probability of confirming all three:

- PO-1: > 95% (defensive coding throughout the module).
- PO-2: ≈ 60% (saturation in the zoo means many axes have
  ``std == 0`` on train, producing point envelopes that any test
  profile with even floating-point drift trips, but those profiles
  are typically ``INSIDE`` the larger non-saturated axes).
- PO-3: ≈ 35% (the strict version is harder: ``UNDEFINED`` is
  common because the zoo has missing ``coherence`` for most
  classes).

The combined probability of confirming the hypothesis is therefore
around **20–30%**. **A REJECTED verdict is the more probable
outcome**, mostly because of LD-4-style trivialities and the zoo's
``coherence`` coverage. As with the coupling experiment, a rejection
here is *informative*: it tells future callers that the
2-sigma default does not generalise out-of-sample on the zoo as
shipped.

---

## Implementation report

First run executed against
`Autonometrics/docs/benchmarks/v0.8.0a0.csv` (n = 645 rows, 31
groups, 5 system classes, 5 canonical axes). For each group the
script materialised a train trajectory from the first
``ceil(0.7 * n_seeds)`` rows (sorted by integer ``seed``) via
`CSVTrajectoryAdapter`, learned an envelope with
`width_multiplier=2.0`, then evaluated every test profile and
counted verdicts.

### Per-class summary of admission

| Class             | groups | trivial (empty env) | non-trivial |
|-------------------|--------|---------------------|-------------|
| `ECASystem`       | 5      | 2 (`rule=90`, `rule=250`) | 3       |
| `KauffmanNetwork` | 5      | 1 (`coupling=0.0`)        | 4       |
| `PeriodicCycle`   | 3      | 0                          | 3       |
| `PromisedCycle`   | 16     | 0                          | 16      |
| `SimpleAutomaton` | 2      | 0                          | 2       |
| **Total**         | **31** | **3**                      | **28**  |

### Aggregate evaluation

Aggregated over the 28 non-trivial groups (157 test profiles total):

| Outcome                  | Count | Fraction |
|--------------------------|-------|----------|
| ``INSIDE``               | 126   | 80.25 %  |
| ``OUTSIDE``              | 10    | 6.37 %   |
| ``UNDEFINED``            | 21    | 13.38 %  |
| ``NOT OUTSIDE`` (PO-2)   | 147   | 93.63 %  |

Predicted outcomes:

| Predicted outcome                                      | Threshold | Observed         | Outcome |
|--------------------------------------------------------|-----------|------------------|---------|
| **PO-1.** script runs to completion                    | —         | runs cleanly     | **PASS** |
| **PO-2.** ≥ 70 % of test profiles are NOT OUTSIDE      | 0.70      | 0.9363            | **PASS** |
| **PO-3.** ≥ 40 % of test profiles are strictly INSIDE  | 0.40      | 0.8025            | **PASS** |

Full per-group output is preserved in
`docs/benchmarks/envelope_v0.4.0a0.csv` and the full stdout in
`docs/benchmarks/envelope_v0.4.0a0.log.txt`.

---

## Verdict

**Hypothesis: CONFIRMED.**

PO-1, PO-2 and PO-3 all hold by comfortable margins. The
2-sigma envelope learned from the first 70 % of a regime's seeds
covers ~80 % of the remaining seeds with a positive ``INSIDE``
verdict, and ~94 % with a non-violating verdict
(``INSIDE`` or ``UNDEFINED``). This is the first **CONFIRMED**
verdict shipped by the public-validation track, after the rejected
[`docs/TURBULENCE_RANKING.md`](TURBULENCE_RANKING.md) and
[`docs/COUPLING_VALIDATION.md`](COUPLING_VALIDATION.md)
experiments.

Three observations worth recording, treated as **observations to
keep in mind**, not as edits to LD-1 through LD-5:

1. **Trivial groups are rare and intelligible.** Only 3 of 31
   groups produce an empty envelope (``ECASystem rule=90``,
   ``ECASystem rule=250``, ``KauffmanNetwork coupling=0.0``). All
   three are known saturation cases of the
   `Autonometrics v0.8.0a0` zoo: every axis lands at the same
   constant for every seed of the train subset, so
   ``from_trajectory`` correctly admits no axis with non-zero
   sample standard deviation. The trivial-group rate is therefore
   a property of the zoo, not the envelope.

2. **OUTSIDE rate is concentrated, not diffuse.** Of the 10
   ``OUTSIDE`` verdicts, 5 come from a single ``KauffmanNetwork``
   pair (``coupling=0.33``, ``coupling=0.5``), where the
   `KauffmanNetwork` regime is known to be metastable. The
   remaining 5 are spread across 5 different ``PromisedCycle``
   parameter sweeps. No class produces a systematic
   ``OUTSIDE`` rate above ~13 %. The envelope is therefore not
   silently failing on any class as a whole.

3. **UNDEFINED is dominated by the ``coherence`` column.** All 21
   ``UNDEFINED`` verdicts come from groups in ``ECASystem`` and
   ``KauffmanNetwork``, where the source CSV reports ``coherence``
   on a non-empty subset of seeds for the train trajectory but
   missing values for some test seeds. The envelope correctly
   propagates ``UNDEFINED`` rather than silently flagging
   ``OUTSIDE`` (LD-4 of the diagnostics document). This confirms
   that mosaic-dropout fielty holds end-to-end on real public
   data.

These findings stand on their own as observations about the
Autonometrics `v0.8.0a0` zoo: the 2-sigma envelope generalises
well across seeds within a regime, the trivial-envelope rate is
fully explained by zoo saturation, and ``UNDEFINED`` propagation
behaves correctly on a real missing-data axis. They do not in
themselves motivate a successor cycle; that decision is left for
whenever a concrete pre-registered design document is ready to
make use of them.

---

## Deviations from pre-registration

None. LD-1 through LD-6 were enforced exactly as committed.
`_TRAIN_FRACTION`, `_WIDTH_MULTIPLIER`,
`_PO2_MIN_NOT_OUTSIDE_FRACTION` and `_PO3_MIN_INSIDE_FRACTION` in
`examples/envelope_validation.py` were not modified between the
pre-registration commit and the run.

---

## References

- Shewhart, W. A. (1931). *Economic Control of Quality of
  Manufactured Product*. Van Nostrand.
- Schölkopf, B., Platt, J. C., Shawe-Taylor, J., Smola, A. J.,
  Williamson, R. C. (2001). "Estimating the Support of a
  High-Dimensional Distribution." *Neural Computation* 13 (7):
  1443-1471.

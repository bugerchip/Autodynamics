# Autodynamics

> **Layer 2 of 3** in the autonomy research trilogy:
> [Autonometrics](https://github.com/bugerchip/Autonometrics) (measure) -> **Autodynamics** (explain) -> Ex-Machina (build / emulate)

**Status:** Pre-alpha. Recording substrate, algebra of trajectories, generic adapters, and Granger-causal coupling primitives. No theoretical model is claimed.

## Vision

`Autonometrics` quantifies *where* a system sits on the five autonomy axes (closure, memory, constraint closure, persistence, coherence). This package gives *mechanical* support for working with *how* those measurements change over time: record ordered profiles, take differences, and summarise motion in the atlas with explicit primitives. It does **not** ship a dynamical *theory* (attractors, phase structure, or predictive claims about autonomy). Interpretation of trajectories as evidence for such a theory is **out of scope** of the public API as it stands; the code is a reproducible toolkit, not a proof.

## What this package contains today

A recording substrate, a small algebra of trajectories, and two
generic input adapters. Together they turn "a sequence of autonomy
measurements" into "a trajectory in a metric space, queryable axis by
axis".

- `ProfileTrajectory` stores a sequence of `AutonomyProfile` values and
  exposes axis-wise time series, pairwise deltas, total path length, and
  the algebra primitives below.
- Algebra primitives: `velocities`, `accelerations`, `drift`,
  `volatility`, `path_length_per_axis`, `rolling_mean`, `rolling_std`,
  and a one-shot per-axis `summary`.
- Adapters: `CSVTrajectoryAdapter` (load from a CSV with canonical
  axis columns) and `BatchTrajectoryAdapter` (build several parallel
  trajectories from grouped profiles, with cross-group `mean_summary`).
- Granger-causal coupling: `granger_graph` (directed pairwise Granger
  graph over admitted axes), `CausalCouplingGraph`, and four scalar
  diagnostics (`symmetry_ratio`, `density`, `max_in_strength`,
  `max_out_strength`).
- Pre-registered boundary regimes and a saturation theorem documented
  in [`docs/TRAJECTORY_DIAGNOSTICS.md`](docs/TRAJECTORY_DIAGNOSTICS.md);
  the coupling protocol is pre-registered in
  [`docs/COUPLING_DIAGNOSTICS.md`](docs/COUPLING_DIAGNOSTICS.md).

> **Install with:** `pip install autodynamics`
> **Import as:** `import autodynamics`

### Quick run

```bash
pip install autodynamics
autodynamics-demo --n-states-list 3 4 5 6 8 --n-steps 600
autodynamics-demo --n-states-list 3 4 5 6 8 --n-steps 600 --report summary
```

The first command prints a small table of `(closure, memory)` profiles
measured over a sweep of `SimpleAutomaton` configurations, the
consecutive deltas between them, and the total path length. The second
prints a per-axis summary instead of the deltas.

## Toy demo: `ProfileTrajectory`

> **Disclaimer.** This is the *recording substrate* of Autodynamics, not its theory. The trajectory class lets you collect, traverse, and compute simple geometric quantities over a sequence of `AutonomyProfile`s. **It does not interpret what those movements mean** — assigning meaning is outside the scope of the public API. Treat the code as a reproducible toolkit or template, not as evidence for a larger claim.

```python
import autonometrics as anm
from autodynamics import ProfileTrajectory

trajectory = ProfileTrajectory(axes=("closure", "memory"))

for n_states in [3, 4, 5, 6, 8]:
    sys = anm.SimpleAutomaton.demo(n_states=n_states, n_steps=600)
    sys.run()
    profile = anm.measure(sys, axes=["closure", "memory"])
    trajectory.append(profile)

print(trajectory.axis_series("closure"))    # time series of one axis
print(trajectory.deltas())                  # pairwise consecutive movements
print(trajectory.total_path_length())       # sum of delta magnitudes
```

## Trajectory algebra

Beyond the substrate, the package exposes an algebra of trajectories
(velocity-style differences, rolling statistics, per-axis summary).
Every primitive is mosaic-dropout fielty: `None` propagates through
differences, but never aborts aggregations.

```python
from autodynamics import ProfileTrajectory

trajectory = ProfileTrajectory(axes=("closure", "memory"))
# ... append profiles as above ...

trajectory.velocities("closure")        # first differences, axis by axis
trajectory.accelerations("closure")     # second differences
trajectory.drift("closure")             # net change between first and last defined values
trajectory.volatility("closure")        # sample std of the velocities
trajectory.path_length_per_axis()       # sum of |velocity| per axis
trajectory.rolling_mean("closure", window=10)  # right-aligned rolling mean
trajectory.rolling_std("closure", window=10)   # right-aligned rolling sample std
trajectory.summary()                    # per-axis report: n_total, n_defined, mean, std, drift, volatility, path_length
```

Calling a primitive without an axis argument returns a dict over every
axis configured on the trajectory; calling it with a canonical axis
name returns the value for that axis directly. The full list of
boundary regimes and the saturation theorem are pre-registered in
[`docs/TRAJECTORY_DIAGNOSTICS.md`](docs/TRAJECTORY_DIAGNOSTICS.md).

## Adapters

Two generic adapters open input paths into `ProfileTrajectory` without
introducing calibration or threshold tuning of their own.

### CSV adapter

```python
from autodynamics import CSVTrajectoryAdapter

adapter = CSVTrajectoryAdapter()
trajectory = adapter.load_path("path/to/profiles.csv")
print(trajectory.summary())
```

The adapter reads columns `closure`, `memory`, `constraint`,
`persistence`, `coherence` (any subset is fine; missing columns yield
fully-undefined axes). Empty or whitespace-only cells become `None`.
Extra columns (`class`, `params`, `seed`, `notes`, ...) are ignored.
Pass `order_column="step"` (or any integer-valued column name) to
sort rows numerically before constructing snapshots.

### Batch adapter

```python
from autodynamics import BatchTrajectoryAdapter
import autonometrics as anm

batch = BatchTrajectoryAdapter()
for params in benchmark_configurations:
    for seed in range(K):
        system = build_system(params, seed)
        system.run()
        profile = anm.measure(system)
        batch.add(params, profile)

trajectories = batch.trajectories()        # one ProfileTrajectory per group key
mean_summary = batch.mean_summary()        # per-axis cross-group means of summary metrics
```

A reproducible end-to-end example using both adapters over a public
fixture is shipped at
[`examples/trajectory_demo.py`](examples/trajectory_demo.py).

## Coupling analysis

Beyond intra-axis algebra, the package exposes a *cross-axis*
primitive: a directed Granger-causal coupling graph between every
pair of admitted axes of a `ProfileTrajectory`, with a stationarity
gate (Augmented Dickey-Fuller), mosaic-dropout-fielty axis
admission, and four scalar diagnostics. The implementation is the
standard pairwise Granger test (Granger 1969; Sims 1980;
Lütkepohl 2005) applied uniformly to the axes of the autonomy
atlas, packaged so it composes with the rest of the algebra
without bespoke calibration.

```python
from autodynamics import (
    granger_graph, density, symmetry_ratio,
    max_in_strength, max_out_strength,
)

graph = granger_graph(trajectory)
# Also accepts a Mapping[str, Sequence[float | None]]:
# graph = granger_graph({"closure": [...], "memory": [...]})

graph.axes_used                                # admitted axes
graph.excluded_axes                            # axis -> rejection reason
graph.edge("closure", "memory").f_stat         # F-stat, lag, p-value, status

symmetry_ratio(graph)                          # average min/max F over pairs
density(graph)                                 # fraction of edges above F critical
max_in_strength(graph, "memory")               # max incoming F-stat
max_out_strength(graph, "closure")             # max outgoing F-stat
```

The protocol (length gate, ADF + up to two differences,
AIC-selected VAR up to `max_lag`, F-test, mosaic-dropout-fielty
axis admission) is pre-registered in
[`docs/COUPLING_DIAGNOSTICS.md`](docs/COUPLING_DIAGNOSTICS.md). It
is **not** a claim that any axis Granger-causes any other axis on
any specific Autonometrics zoo; it is a composable primitive that
can be fed real or synthetic trajectories without bespoke threshold
tuning.

## Public validation track

Pre-registered, falsifiable experiments that stress the algebra
primitives against the public Autonometrics benchmarks. Each
experiment locks its hypothesis in `docs/` before any output is
generated, and records both confirmations and rejections verbatim.
Recent public runs include **negative results**: they narrow what the
current primitives can support and are not written as motivation for a
new public release cycle.

- [`docs/TURBULENCE_RANKING.md`](docs/TURBULENCE_RANKING.md) — pre-registered
  ranking of the five Autonometrics zoo classes by cross-seed
  volatility on the `v0.8.0a0` benchmark. Reproducible from
  [`examples/turbulence_ranking.py`](examples/turbulence_ranking.py); raw
  outputs in [`docs/benchmarks/turbulence_ranking_v0.2.1a0.csv`](docs/benchmarks/turbulence_ranking_v0.2.1a0.csv)
  and the full log in
  [`docs/benchmarks/turbulence_ranking_v0.2.1a0.log.txt`](docs/benchmarks/turbulence_ranking_v0.2.1a0.log.txt).
  Verdict: REJECTED.
- [`docs/COUPLING_VALIDATION.md`](docs/COUPLING_VALIDATION.md) — pre-registered
  Granger coupling experiment running `granger_graph` against every
  group of the same `v0.8.0a0` zoo. Reproducible from
  [`examples/coupling_validation.py`](examples/coupling_validation.py); raw
  outputs in [`docs/benchmarks/coupling_v0.3.0a0.csv`](docs/benchmarks/coupling_v0.3.0a0.csv)
  and the full log in
  [`docs/benchmarks/coupling_v0.3.0a0.log.txt`](docs/benchmarks/coupling_v0.3.0a0.log.txt).
  Verdict: REJECTED, by a single group below the admission threshold
  (15 of 31 groups admit ≥ 2 axes against a 50 % bar). The pipeline
  itself is robust (93 % of admitted edges produce finite
  F-statistics); the bottleneck is the saturation pattern of the
  source zoo.

## Roadmap

- `v0.1.0a0` / `v0.1.0a1`: Toy trajectory recorder. Reserves name, declares vision, ships demo.
- `v0.2.0a0`: Trajectory algebra (velocities, accelerations, drift, volatility, rolling statistics, summary), generic CSV / batch adapters, pre-registered diagnostics, public validation track.
- `v0.2.1a0`: Documentation cleanup; PyPI summary description shortened.
- `v0.3.0a0` *(current)*: Granger-causal coupling primitives (`granger_graph`, `CausalCouplingGraph`, four scalar diagnostics), with pre-registered diagnostics ([`docs/COUPLING_DIAGNOSTICS.md`](docs/COUPLING_DIAGNOSTICS.md)) and public validation track ([`docs/COUPLING_VALIDATION.md`](docs/COUPLING_VALIDATION.md), verdict: REJECTED).
- `v0.4.0a0` *(planned)*: Generic envelope primitives (`Envelope`, trinary `ContainmentVerdict`) with the same pre-registration / public-validation discipline.

Beyond `v0.4.0a0`, no further cycle is pre-declared. Future work will be opened only when motivated by a concrete pre-registered design document or external collaboration.

## Position in the trilogy

| Layer | Project | Question it answers |
|---|---|---|
| 1 | [Autonometrics](https://github.com/bugerchip/Autonometrics) | *Where* does a system sit on the autonomy atlas? |
| 2 | **Autodynamics** | *How* do successive profiles differ, and how do their axes couple (recorded motion plus pairwise Granger coupling, not a dynamical model)? |
| 3 | Ex-Machina | *Can we build* a system that occupies a chosen region? |

## License

Apache License 2.0 — see [LICENSE](LICENSE).

## Citation

If you reference this work, please cite Autodynamics directly. A formal citation block will be added when the API stabilises.

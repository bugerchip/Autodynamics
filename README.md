# Autodynamics

> **Layer 2 of 3** in the autonomy research trilogy:
> [Autonometrics](https://github.com/bugerchip/Autonometrics) (measure) -> **Autodynamics** (explain) -> [Ex-Machina](https://github.com/bugerchip/Ex-Machina) (build / emulate)

**Status:** Pre-alpha. Ships a recording substrate; no stable theoretical model yet.

## Vision

`Autonometrics` quantifies *where* a system sits on the five autonomy axes (closure, memory, constraint closure, persistence, coherence). `Autodynamics` aims to model *how* systems move across that atlas: trajectories, attractors, transitions, and the dynamical regularities that govern changes in autonomy.

This package will eventually expose:

- Trajectory analysis tools over `AutonomyProfile` time series.
- Phase-space modelling for systems described by the `AutonomySystem` protocol.
- Stability and attractor characterisation across the five-axis atlas.
- Hooks for empirical validation against longitudinal data from biology, AI, and motivational psychology corpora.

## What this package contains today

A minimal recording substrate: `ProfileTrajectory`. A class that:

1. Stores a sequence of `AutonomyProfile` values measured at successive moments.
2. Exposes axis-wise time series for any of the five canonical axes.
3. Computes pairwise consecutive deltas.
4. Sums the resulting magnitudes into a total path length in profile space.

It is the smallest piece of code that lets you treat **a sequence of autonomy measurements as a trajectory in a metric space** — the precondition for any later dynamical analysis.

> **Install with:** `pip install autodynamics`
> **Import as:** `import autodynamics`

### Quick run

```bash
pip install autodynamics
autodynamics-demo --n-states-list 3 4 5 6 8 --n-steps 600
```

You will see a small table of `(closure, memory)` profiles measured over a sweep of `SimpleAutomaton` configurations, the consecutive deltas between them, and the total path length.

## Toy demo: `ProfileTrajectory`

> **Disclaimer.** This is the *recording substrate* of Autodynamics, not its theory. The trajectory class lets you collect, traverse, and compute simple geometric quantities over a sequence of `AutonomyProfile`s. **It does not interpret what those movements mean** — that interpretation is the open research question this package will eventually try to answer. Treat the code as a useful template, not as evidence.

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

## Roadmap

- `v0.1.0a0` *(current)*: Toy trajectory recorder. Reserves name, declares vision, ships demo.
- `v0.2.x`: First serious dynamics primitives (attractor characterisation, regime classification). Lands after Autonometrics reaches v1.0.
- `v1.0.0`: Stable trajectory API on top of Autonometrics profiles.

## Position in the trilogy

| Layer | Project | Question it answers |
|---|---|---|
| 1 | [Autonometrics](https://github.com/bugerchip/Autonometrics) | *Where* does a system sit on the autonomy atlas? |
| 2 | **Autodynamics** | *How* does it move across the atlas over time? |
| 3 | [Ex-Machina](https://github.com/bugerchip/Ex-Machina) | *Can we build* a system that occupies a chosen region? |

## License

Apache License 2.0 — see [LICENSE](LICENSE).

## Citation

If you reference this work, please cite the trilogy as a whole. A formal citation block will be added in `v0.2.x`.

"""Autodynamics: modelling autonomy dynamics over the Autonometrics atlas.

Layer 2 of the Autonometrics -> Autodynamics -> Ex-Machina trilogy.

Public API in v0.1.0a0:

- :class:`ProfileTrajectory` — a time series of autonomy profiles, with
  utilities to read axis-wise series, compute pairwise consecutive
  deltas, and sum the resulting path length in profile space.
- :class:`ProfileSnapshot` — a single recorded measurement.
- :class:`ProfileDelta` — the pairwise difference between two snapshots
  with a Euclidean magnitude over its defined axes.

This is the *recording substrate* of Autodynamics, not its theory. The
trajectory class lets you collect, traverse, and compute simple
geometric quantities over a sequence of AutonomyProfile values. It does
not interpret what those movements mean — that interpretation is the
open research question this package will eventually try to answer.
"""

from autodynamics.trajectory import (
    ProfileDelta,
    ProfileSnapshot,
    ProfileTrajectory,
)

__version__ = "0.1.0a0"

__all__ = [
    "ProfileDelta",
    "ProfileSnapshot",
    "ProfileTrajectory",
    "__version__",
]

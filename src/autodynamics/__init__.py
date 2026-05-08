"""Autodynamics: modelling autonomy dynamics over the Autonometrics atlas.

Layer 2 of the Autonometrics -> Autodynamics -> Ex-Machina trilogy.

Public API:

- :class:`ProfileTrajectory` — a time series of autonomy profiles.
  Beyond the recording substrate (axis-wise series, pairwise deltas,
  total path length), exposes an algebra of trajectories:
  ``velocities``, ``accelerations``, ``drift``, ``volatility``,
  ``path_length_per_axis``, ``rolling_mean``, ``rolling_std`` and a
  one-shot per-axis ``summary``.
- :class:`ProfileSnapshot` — a single recorded measurement.
- :class:`ProfileDelta` — pairwise difference with Euclidean magnitude.
- :class:`CSVTrajectoryAdapter` — load a trajectory from a CSV with
  canonical axis columns.
- :class:`BatchTrajectoryAdapter` — build several parallel trajectories
  from grouped profiles, with per-axis cross-group ``mean_summary``.

This is the *recording substrate plus algebra* of Autodynamics, not its
theory. Every primitive is mosaic-dropout fielty: ``None`` propagates
through differences, but never aborts aggregations. Pre-registered
boundary regimes and a saturation theorem are documented in
``docs/TRAJECTORY_DIAGNOSTICS.md``.
"""

from autodynamics.adapters import (
    BatchTrajectoryAdapter,
    CSVTrajectoryAdapter,
)
from autodynamics.trajectory import (
    ProfileDelta,
    ProfileSnapshot,
    ProfileTrajectory,
)

__version__ = "0.2.1a0"

__all__ = [
    "BatchTrajectoryAdapter",
    "CSVTrajectoryAdapter",
    "ProfileDelta",
    "ProfileSnapshot",
    "ProfileTrajectory",
    "__version__",
]

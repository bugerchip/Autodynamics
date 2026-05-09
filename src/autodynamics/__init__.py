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
- :class:`CausalCouplingGraph`, :class:`CausalCouplingResult`,
  :func:`granger_coupling`, :func:`granger_graph`,
  :func:`symmetry_ratio`, :func:`density`, :func:`max_in_strength`,
  :func:`max_out_strength` — Granger-causal coupling analysis over
  trajectories. See :mod:`autodynamics.coupling`.
- :class:`Envelope`, :class:`ContainmentResult`,
  :class:`ContainmentVerdict` — per-axis admissible-region check
  with a trinary verdict (``INSIDE`` / ``OUTSIDE`` / ``UNDEFINED``).
  See :mod:`autodynamics.envelope`.

This is the *recording substrate plus algebra* of Autodynamics, not a
dynamical theory. Every primitive is mosaic-dropout fielty: ``None``
propagates through differences, but never aborts aggregations.
Pre-registered boundary regimes and the saturation theorem are
documented in ``docs/TRAJECTORY_DIAGNOSTICS.md``; the Granger
coupling protocol is documented in ``docs/COUPLING_DIAGNOSTICS.md``;
the envelope containment protocol is documented in
``docs/ENVELOPE_DIAGNOSTICS.md``.
"""

from autodynamics.adapters import (
    BatchTrajectoryAdapter,
    CSVTrajectoryAdapter,
)
from autodynamics.coupling import (
    CausalCouplingGraph,
    CausalCouplingResult,
    density,
    granger_coupling,
    granger_graph,
    max_in_strength,
    max_out_strength,
    symmetry_ratio,
)
from autodynamics.envelope import (
    ContainmentResult,
    ContainmentVerdict,
    Envelope,
)
from autodynamics.trajectory import (
    ProfileDelta,
    ProfileSnapshot,
    ProfileTrajectory,
)

__version__ = "0.4.0a0"

__all__ = [
    "BatchTrajectoryAdapter",
    "CSVTrajectoryAdapter",
    "CausalCouplingGraph",
    "CausalCouplingResult",
    "ContainmentResult",
    "ContainmentVerdict",
    "Envelope",
    "ProfileDelta",
    "ProfileSnapshot",
    "ProfileTrajectory",
    "__version__",
    "density",
    "granger_coupling",
    "granger_graph",
    "max_in_strength",
    "max_out_strength",
    "symmetry_ratio",
]

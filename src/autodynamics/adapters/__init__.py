"""Generic input adapters for ``ProfileTrajectory``.

This subpackage hosts adapters that turn external sources of autonomy
profiles into trajectories without committing to any single domain.
The two adapters shipped in ``v0.2.0a0`` are:

- :class:`CSVTrajectoryAdapter`: load a trajectory from a CSV with
  canonical axis columns.
- :class:`BatchTrajectoryAdapter`: build several parallel trajectories
  from grouped profiles.

Domain-specific adapters (real-time streams, proprietary log
formats, application-specific schemas) are explicitly out of scope
for the public library; they belong to downstream products that
build on top of Autodynamics.
"""

from autodynamics.adapters.batch import BatchTrajectoryAdapter
from autodynamics.adapters.csv_trajectory import CSVTrajectoryAdapter

__all__ = [
    "BatchTrajectoryAdapter",
    "CSVTrajectoryAdapter",
]

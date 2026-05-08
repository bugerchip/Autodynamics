"""Batch adapter for parallel ``ProfileTrajectory`` construction.

Use case: given a benchmark with ``N`` groups (e.g. ``(class, params)``
combinations) and ``K`` measurements per group (e.g. seeds, time
windows, snapshots), build one :class:`ProfileTrajectory` per group
and provide light cross-group aggregation that does not introduce
calibration or thresholds of its own.

Aggregation is intentionally narrow: only ``mean_summary`` is shipped
in ``v0.2.0a0``, and it averages the per-axis ``summary()`` metrics
across groups. Any heavier statistic (cross-group correlation,
coupling, divergence) is deferred to later cycles where it earns a
pre-registered design document.
"""

from __future__ import annotations

import math
from collections.abc import Hashable, Iterable
from typing import TypeVar

from autonometrics import AutonomyProfile

from autodynamics.trajectory import ProfileTrajectory

K = TypeVar("K", bound=Hashable)

_CANONICAL_AXES: tuple[str, ...] = (
    "closure",
    "memory",
    "constraint",
    "persistence",
    "coherence",
)
_SUMMARY_METRICS: tuple[str, ...] = (
    "mean",
    "std",
    "drift",
    "volatility",
    "path_length",
)


class BatchTrajectoryAdapter:
    """Build a batch of parallel ``ProfileTrajectory`` objects.

    Parameters
    ----------
    axes:
        Forwarded to every :class:`ProfileTrajectory` constructed by
        :meth:`trajectories`. Defaults to ``None`` (all five canonical
        axes).

    Notes
    -----
    The adapter stores profiles per group key in insertion order, so
    callers who need a particular ordinal (seed, timestep) should add
    profiles already sorted, or reset and rebuild the batch. Holding
    the order outside this class keeps the batch class agnostic about
    what ``time`` means in any given experiment.
    """

    def __init__(self, *, axes: Iterable[str] | None = None) -> None:
        self._axes = None if axes is None else tuple(axes)
        self._groups: dict[Hashable, list[AutonomyProfile]] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add(self, group_key: Hashable, profile: AutonomyProfile) -> None:
        """Register a profile under the given group key.

        ``group_key`` may be any hashable value. Profiles added to the
        same key are kept in insertion order; the order across keys
        follows first-insertion of each key.
        """
        self._groups.setdefault(group_key, []).append(profile)

    # ------------------------------------------------------------------
    # Reading
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._groups)

    @property
    def group_keys(self) -> tuple[Hashable, ...]:
        """Group keys in first-insertion order."""
        return tuple(self._groups.keys())

    def trajectories(self) -> dict[Hashable, ProfileTrajectory]:
        """Materialise one :class:`ProfileTrajectory` per group key.

        Each call builds fresh trajectory objects from the profiles
        stored in this batch; the batch itself is not mutated.
        """
        out: dict[Hashable, ProfileTrajectory] = {}
        for key, profiles in self._groups.items():
            traj = ProfileTrajectory(axes=self._axes)
            for profile in profiles:
                traj.append(profile)
            out[key] = traj
        return out

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def mean_summary(self) -> dict[str, dict[str, float | None]]:
        """Mean of ``summary()`` metrics across groups, axis by axis.

        For each canonical axis and each metric in
        ``{mean, std, drift, volatility, path_length}``, returns the
        arithmetic mean of the per-group values, taken over the groups
        whose value is not ``None``. Returns ``None`` for that
        ``(axis, metric)`` pair when **every** group reports ``None``.

        Counts (``n_total``, ``n_defined``) are intentionally omitted:
        averaging counts across heterogeneous groups would mix
        sample sizes with metric values and is left to the caller.
        """
        per_axis: dict[str, dict[str, float | None]] = {}
        trajectories = self.trajectories()

        if not trajectories:
            for axis in _CANONICAL_AXES:
                per_axis[axis] = {metric: None for metric in _SUMMARY_METRICS}
            return per_axis

        per_group_summaries = [
            traj.summary() for traj in trajectories.values()
        ]

        for axis in _CANONICAL_AXES:
            axis_means: dict[str, float | None] = {}
            for metric in _SUMMARY_METRICS:
                values: list[float] = []
                for summary in per_group_summaries:
                    value = summary[axis][metric]
                    if isinstance(value, (int, float)) and not isinstance(
                        value, bool
                    ):
                        as_float = float(value)
                        if math.isfinite(as_float):
                            values.append(as_float)
                if values:
                    axis_means[metric] = float(sum(values) / len(values))
                else:
                    axis_means[metric] = None
            per_axis[axis] = axis_means

        return per_axis

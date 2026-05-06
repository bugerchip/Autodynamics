"""Trajectory recorder for autonomy profiles.

This module ships the smallest piece of code that lets a caller treat a
sequence of :class:`autonometrics.AutonomyProfile` values as a
trajectory in a metric space: store the sequence, read it axis by axis,
compute pairwise consecutive deltas, and sum the resulting magnitudes
into a total path length.

The class is the *recording substrate* of Autodynamics; it does not
interpret what the recorded movements mean. That interpretation is the
open research question this package will eventually try to answer.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from autonometrics import AutonomyProfile

_CANONICAL_AXES: tuple[str, ...] = (
    "closure",
    "memory",
    "constraint",
    "persistence",
    "coherence",
)


@dataclass(frozen=True)
class ProfileSnapshot:
    """A single :class:`autonometrics.AutonomyProfile` recorded at an index.

    Attributes
    ----------
    index:
        Position of this snapshot in the parent
        :class:`ProfileTrajectory` (0-based).
    profile:
        The autonomy profile measured at this point.
    """

    index: int
    profile: AutonomyProfile


@dataclass(frozen=True)
class ProfileDelta:
    """Pairwise difference between two consecutive snapshots, axis by axis.

    The ``deltas`` mapping has one entry per canonical axis tracked by
    the parent :class:`ProfileTrajectory`. Each value is:

    - ``current_value - previous_value`` if both endpoints have the axis
      defined, or
    - ``None`` if either endpoint reports ``None`` for the axis (mosaic
      dropout policy inherited from Autonometrics).

    Attributes
    ----------
    from_index:
        Index of the earlier snapshot.
    to_index:
        Index of the later snapshot.
    deltas:
        Mapping ``{canonical_axis: float | None}``.
    """

    from_index: int
    to_index: int
    deltas: dict[str, float | None]

    @property
    def magnitude(self) -> float | None:
        """Euclidean magnitude over the fully-defined axes only.

        Returns ``None`` if every axis in ``deltas`` is ``None``.
        Otherwise returns the Euclidean norm computed over the defined
        deltas, ignoring the ``None`` entries.
        """
        defined = [v for v in self.deltas.values() if v is not None]
        if not defined:
            return None
        return float(math.sqrt(sum(v * v for v in defined)))


class ProfileTrajectory:
    """Time series of autonomy profiles over the same or comparable systems.

    Stores :class:`ProfileSnapshot` values in append order and exposes
    utilities for reading them as time series, computing pairwise
    consecutive deltas, and summing path length.

    The class does not interpret what the recorded movements mean — that
    is the open research question this package will eventually try to
    answer. Use it as a recording substrate, not as evidence.

    Parameters
    ----------
    axes:
        Iterable of canonical axis names this trajectory will report on.
        Defaults to all five canonical axes when ``None``. Profiles
        appended to the trajectory may carry data on other axes; the
        ``axes`` argument only bounds which axes are reported by
        :meth:`axis_series`, :meth:`deltas`, and :meth:`to_dict`.

    Raises
    ------
    ValueError
        If ``axes`` is a non-``None`` iterable that is empty, contains a
        name not in the canonical set, or contains duplicates.
    """

    def __init__(self, axes: Iterable[str] | None = None) -> None:
        if axes is None:
            self._axes: tuple[str, ...] = _CANONICAL_AXES
        else:
            seen: set[str] = set()
            normalised: list[str] = []
            for axis in axes:
                if axis not in _CANONICAL_AXES:
                    raise ValueError(
                        f"Unknown axis {axis!r}. Canonical axes: {_CANONICAL_AXES}"
                    )
                if axis in seen:
                    raise ValueError(f"Duplicate axis {axis!r} in axes argument")
                seen.add(axis)
                normalised.append(axis)
            if not normalised:
                raise ValueError("axes must contain at least one entry when provided")
            self._axes = tuple(normalised)
        self._snapshots: list[ProfileSnapshot] = []

    # ------------------------------------------------------------------
    # Sequence-like access
    # ------------------------------------------------------------------

    def append(self, profile: AutonomyProfile) -> ProfileSnapshot:
        """Append a profile to the trajectory and return its snapshot.

        The new snapshot's ``index`` is ``len(self)`` *before* the
        append.
        """
        snapshot = ProfileSnapshot(index=len(self._snapshots), profile=profile)
        self._snapshots.append(snapshot)
        return snapshot

    def __len__(self) -> int:
        return len(self._snapshots)

    def __getitem__(self, i: int) -> ProfileSnapshot:
        return self._snapshots[i]

    def __iter__(self) -> Iterator[ProfileSnapshot]:
        return iter(self._snapshots)

    # ------------------------------------------------------------------
    # Reading the trajectory
    # ------------------------------------------------------------------

    @property
    def axes(self) -> tuple[str, ...]:
        """Canonical axes this trajectory reports on."""
        return self._axes

    def axis_series(self, axis: str) -> list[float | None]:
        """Return the time series of a single canonical axis.

        Each entry is the value of the named axis at the corresponding
        snapshot, or ``None`` if that snapshot reports ``None`` for the
        axis (mosaic dropout).
        """
        if axis not in _CANONICAL_AXES:
            raise ValueError(
                f"Unknown axis {axis!r}. Canonical axes: {_CANONICAL_AXES}"
            )
        return [s.profile[axis] for s in self._snapshots]

    def deltas(self) -> list[ProfileDelta]:
        """Pairwise consecutive deltas across the configured ``axes``.

        Returns a list of length ``max(len(self) - 1, 0)``. Empty list
        if fewer than two snapshots have been appended.
        """
        result: list[ProfileDelta] = []
        for i in range(1, len(self._snapshots)):
            prev = self._snapshots[i - 1].profile
            curr = self._snapshots[i].profile
            entries: dict[str, float | None] = {}
            for axis in self._axes:
                pv = prev[axis]
                cv = curr[axis]
                entries[axis] = (
                    (cv - pv)
                    if (pv is not None and cv is not None)
                    else None
                )
            result.append(
                ProfileDelta(from_index=i - 1, to_index=i, deltas=entries)
            )
        return result

    def total_path_length(self) -> float | None:
        """Sum of consecutive delta magnitudes along the trajectory.

        Returns ``None`` if the trajectory has fewer than two snapshots
        or if every consecutive delta has no fully-defined axis. Deltas
        whose ``magnitude`` is ``None`` are skipped, never aborting the
        sum.
        """
        deltas = self.deltas()
        if not deltas:
            return None
        magnitudes = [d.magnitude for d in deltas if d.magnitude is not None]
        if not magnitudes:
            return None
        return float(sum(magnitudes))

    def to_dict(self) -> dict[str, list[float | None]]:
        """Serialise the trajectory to a dictionary of axis-wise series.

        Output shape: ``{axis_name: [value_or_None_per_snapshot, ...]}``.
        Stable for JSON serialisation (every value is ``float`` or
        ``None``).
        """
        return {axis: self.axis_series(axis) for axis in self._axes}

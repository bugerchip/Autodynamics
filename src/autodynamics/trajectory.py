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

    # ------------------------------------------------------------------
    # Algebra primitives (added in v0.2.0a0)
    # ------------------------------------------------------------------

    def velocities(
        self, axis: str | None = None
    ) -> dict[str, list[float | None]] | list[float | None]:
        """First differences of the axis-wise series.

        For each axis, returns a list of length ``max(len(self) - 1, 0)``
        whose ``i``-th entry is ``series[i + 1] - series[i]``, or ``None``
        if either endpoint is ``None`` (mosaic dropout).

        Parameters
        ----------
        axis:
            If ``None`` (default), return a dict ``{axis: [...]}`` over
            every axis configured on this trajectory. If a canonical
            axis name is given, return only that axis' list.
        """
        if axis is None:
            return {a: self._velocities_for(a) for a in self._axes}
        self._validate_axis(axis)
        return self._velocities_for(axis)

    def accelerations(
        self, axis: str | None = None
    ) -> dict[str, list[float | None]] | list[float | None]:
        """Second differences of the axis-wise series.

        Defined as the first differences of :meth:`velocities`. Each
        list has length ``max(len(self) - 2, 0)``. ``None`` propagates
        if either endpoint of the velocity pair is ``None``.

        Parameters
        ----------
        axis:
            See :meth:`velocities`.
        """
        if axis is None:
            return {a: self._accelerations_for(a) for a in self._axes}
        self._validate_axis(axis)
        return self._accelerations_for(axis)

    def drift(
        self, axis: str | None = None
    ) -> dict[str, float | None] | float | None:
        """Net change between the first and last *defined* values of an axis.

        Skips ``None`` slots: if the axis has values
        ``[None, 0.3, 0.5, None, 0.7]``, the drift is ``0.7 - 0.3 = 0.4``.

        Returns ``None`` for an axis with fewer than two defined values
        (a single defined value, or a fully-undefined axis, both yield
        ``None``).
        """
        if axis is None:
            return {a: self._drift_for(a) for a in self._axes}
        self._validate_axis(axis)
        return self._drift_for(axis)

    def volatility(
        self, axis: str | None = None
    ) -> dict[str, float | None] | float | None:
        """Sample standard deviation (``ddof=1``) of an axis' velocities.

        Operates on the *velocities*, not on the raw values, so a strictly
        monotone trajectory has positive ``drift`` but zero ``volatility``
        when its velocities are constant.

        Returns ``None`` if the axis has fewer than two defined velocities
        (sample variance is undefined for a single observation).
        """
        if axis is None:
            return {a: self._volatility_for(a) for a in self._axes}
        self._validate_axis(axis)
        return self._volatility_for(axis)

    def path_length_per_axis(self) -> dict[str, float | None]:
        """Sum of absolute velocities, axis by axis.

        For each axis, sums ``|v|`` over the defined velocities, skipping
        ``None`` slots (consistent with :meth:`total_path_length`).

        Returns ``None`` for an axis whose velocities are all ``None``
        (fully-undefined or single-snapshot trajectories).
        """
        return {a: self._path_length_for(a) for a in self._axes}

    def rolling_mean(self, axis: str, window: int) -> list[float | None]:
        """Right-aligned (trailing) rolling mean over a single axis.

        For each position ``i``, the window covers ``series[i - window + 1 : i + 1]``.
        Output positions ``0 .. window - 2`` are always ``None`` (the
        window does not yet fit). For positions ``i >= window - 1``,
        emits the mean of the defined values inside the window when at
        least ``ceil(window / 2)`` of them are defined; otherwise ``None``.

        ``window > len(self)`` produces a list of all ``None``.
        """
        self._validate_axis(axis)
        self._validate_window(window)
        return self._rolling(self.axis_series(axis), window, op="mean")

    def rolling_std(self, axis: str, window: int) -> list[float | None]:
        """Right-aligned (trailing) rolling sample std (``ddof=1``).

        Same windowing and ``ceil(window / 2)`` rule as
        :meth:`rolling_mean`. Additionally, a window with fewer than two
        defined values emits ``None`` (sample std is undefined).
        """
        self._validate_axis(axis)
        self._validate_window(window)
        return self._rolling(self.axis_series(axis), window, op="std")

    def summary(self) -> dict[str, dict[str, float | int | None]]:
        """One-shot per-axis report.

        Returns a dict ``{axis: {metric: value}}`` where ``metric`` is one
        of ``n_total`` (``int``), ``n_defined`` (``int``), ``mean``,
        ``std``, ``drift``, ``volatility``, ``path_length``. Numeric
        metrics are ``float`` or ``None`` following the same mosaic
        dropout rules as the standalone methods. ``mean`` and ``std`` are
        computed over the raw values; ``volatility`` over the velocities.
        """
        out: dict[str, dict[str, float | int | None]] = {}
        n_total = len(self._snapshots)
        for axis in self._axes:
            series = self.axis_series(axis)
            defined = [v for v in series if v is not None]
            n_defined = len(defined)
            if n_defined == 0:
                mean_v: float | None = None
            else:
                mean_v = float(sum(defined) / n_defined)
            if n_defined >= 2:
                mu = sum(defined) / n_defined
                var = sum((v - mu) ** 2 for v in defined) / (n_defined - 1)
                std_v: float | None = float(math.sqrt(var))
            else:
                std_v = None
            out[axis] = {
                "n_total": n_total,
                "n_defined": n_defined,
                "mean": mean_v,
                "std": std_v,
                "drift": self._drift_for(axis),
                "volatility": self._volatility_for(axis),
                "path_length": self._path_length_for(axis),
            }
        return out

    # ------------------------------------------------------------------
    # Internal helpers (algebra primitives)
    # ------------------------------------------------------------------

    def _validate_axis(self, axis: str) -> None:
        if axis not in _CANONICAL_AXES:
            raise ValueError(
                f"Unknown axis {axis!r}. Canonical axes: {_CANONICAL_AXES}"
            )

    def _validate_window(self, window: int) -> None:
        if isinstance(window, bool) or not isinstance(window, int):
            raise TypeError(
                f"window must be a positive int, got {type(window).__name__}"
            )
        if window < 1:
            raise ValueError(f"window must be >= 1, got {window}")

    def _velocities_for(self, axis: str) -> list[float | None]:
        series = self.axis_series(axis)
        if len(series) < 2:
            return []
        out: list[float | None] = []
        for prev, curr in zip(series[:-1], series[1:]):
            if prev is None or curr is None:
                out.append(None)
            else:
                out.append(float(curr - prev))
        return out

    def _accelerations_for(self, axis: str) -> list[float | None]:
        velocities = self._velocities_for(axis)
        if len(velocities) < 2:
            return []
        out: list[float | None] = []
        for prev, curr in zip(velocities[:-1], velocities[1:]):
            if prev is None or curr is None:
                out.append(None)
            else:
                out.append(float(curr - prev))
        return out

    def _drift_for(self, axis: str) -> float | None:
        series = self.axis_series(axis)
        defined = [v for v in series if v is not None]
        if len(defined) < 2:
            return None
        return float(defined[-1] - defined[0])

    def _volatility_for(self, axis: str) -> float | None:
        velocities = self._velocities_for(axis)
        defined = [v for v in velocities if v is not None]
        if len(defined) < 2:
            return None
        mu = sum(defined) / len(defined)
        var = sum((v - mu) ** 2 for v in defined) / (len(defined) - 1)
        return float(math.sqrt(var))

    def _path_length_for(self, axis: str) -> float | None:
        velocities = self._velocities_for(axis)
        defined_abs = [abs(v) for v in velocities if v is not None]
        if not defined_abs:
            return None
        return float(sum(defined_abs))

    def _rolling(
        self,
        series: list[float | None],
        window: int,
        op: str,
    ) -> list[float | None]:
        n = len(series)
        min_defined = math.ceil(window / 2)
        out: list[float | None] = []
        for i in range(n):
            if i < window - 1:
                out.append(None)
                continue
            window_slice = series[i - window + 1 : i + 1]
            defined = [v for v in window_slice if v is not None]
            if len(defined) < min_defined:
                out.append(None)
                continue
            if op == "mean":
                out.append(float(sum(defined) / len(defined)))
            elif op == "std":
                if len(defined) < 2:
                    out.append(None)
                    continue
                mu = sum(defined) / len(defined)
                var = sum((v - mu) ** 2 for v in defined) / (len(defined) - 1)
                out.append(float(math.sqrt(var)))
            else:  # pragma: no cover — guarded by callers
                raise ValueError(f"unknown rolling op {op!r}")
        return out

    def to_dict(self) -> dict[str, list[float | None]]:
        """Serialise the trajectory to a dictionary of axis-wise series.

        Output shape: ``{axis_name: [value_or_None_per_snapshot, ...]}``.
        Stable for JSON serialisation (every value is ``float`` or
        ``None``).
        """
        return {axis: self.axis_series(axis) for axis in self._axes}

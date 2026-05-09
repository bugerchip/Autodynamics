"""Directed causal coupling graph and trajectory-aware constructor.

This module ships the graph-level objects on top of pairwise Granger
results from :mod:`autodynamics.coupling.granger`:

- :class:`CausalCouplingGraph`: a directed graph whose nodes are the
  axes admitted by the dropout / saturation gates, and whose edges
  carry per-pair :class:`autodynamics.coupling.granger.CausalCouplingResult`
  values.
- :func:`granger_graph`: the public entry point. Accepts either a
  :class:`autodynamics.ProfileTrajectory` or a mapping
  ``{axis_name: series}`` and applies the dropout / saturation /
  longest-contiguous-subseries policy documented in
  ``docs/COUPLING_DIAGNOSTICS.md`` before delegating to pairwise
  Granger.

The mosaic-dropout policy mirrors the one already used elsewhere in
``autodynamics``: ``None`` (or ``NaN``) values are not silently
dropped and re-stitched. The caller picks the longest contiguous run
of defined values inside each axis and only that run is used for the
Granger fit. This preserves the temporal structure that VAR estimation
depends on.

References:

- Granger, C. W. J. (1969). "Investigating Causal Relations by
  Econometric Models and Cross-spectral Methods." *Econometrica*
  37 (3): 424-438.
- Sims, C. A. (1980). "Macroeconomics and Reality." *Econometrica*
  48 (1): 1-48.
- Lutkepohl, H. (2005). *New Introduction to Multiple Time Series
  Analysis*. Springer.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Union

import numpy as np

from autodynamics.coupling.granger import (
    DEFAULT_MAX_LAG,
    DEFAULT_N_MIN,
    CausalCouplingResult,
    granger_coupling,
)
from autodynamics.trajectory import ProfileTrajectory

DEFAULT_MOSAIC_THRESHOLD = 0.8
DEFAULT_SATURATION_TOL = 1e-12

# Type alias for the two accepted source shapes.
GrangerGraphSource = Union[
    ProfileTrajectory,
    Mapping[str, Sequence[float | None]],
    Mapping[str, np.ndarray],
]


@dataclass(frozen=True)
class CausalCouplingGraph:
    """Directed Granger-causal coupling graph over a set of axes.

    Attributes
    ----------
    edges:
        Dictionary keyed by ``(a, b)`` with ``a != b``; the value is
        the :class:`autodynamics.coupling.granger.CausalCouplingResult`
        for the direction ``a -> b``.
    axes_used:
        Axis names that survived the admission gate (sufficient
        defined samples, sufficient mosaic coverage, non-saturated).
    excluded_axes:
        Mapping from axis name to a string explaining why it was
        excluded (saturation, mosaic dropout, too few defined samples,
        empty input, sub-series too short after dropout).
    null_pairs:
        Pairs ``(a, b)`` for which the F-stat is ``None`` even though
        both axes were admitted (VAR or F-test failed for that pair).
    n_obs_min:
        Minimum effective sample size across all admitted edges.
        ``0`` if no edge produced a numeric result.
    """

    edges: Mapping[tuple[str, str], CausalCouplingResult]
    axes_used: tuple[str, ...]
    excluded_axes: Mapping[str, str]
    null_pairs: tuple[tuple[str, str], ...]
    n_obs_min: int

    def edge(self, a: str, b: str) -> CausalCouplingResult:
        """Return the ``a -> b`` edge; raises ``KeyError`` if absent."""
        return self.edges[(a, b)]


def _longest_contiguous_run(series: Sequence[float | None]) -> tuple[int, int]:
    """Return inclusive bounds of the longest run with no ``None`` / ``NaN``.

    Returns ``(-1, -1)`` if the series is empty or fully missing.
    Ties broken in favour of the earliest occurrence.
    """
    best_start, best_end = -1, -1
    best_len = 0
    cur_start: int | None = None

    for i, v in enumerate(series):
        is_missing = v is None or (isinstance(v, float) and not np.isfinite(v))
        if is_missing:
            cur_start = None
            continue
        if cur_start is None:
            cur_start = i
        cur_len = i - cur_start + 1
        if cur_len > best_len:
            best_len = cur_len
            best_start = cur_start
            best_end = i

    return best_start, best_end


def _series_to_floatlist(series: object) -> list[float | None]:
    """Coerce a series-like input to a uniform ``list[float | None]``.

    Accepts ``Sequence[float | None]`` or ``np.ndarray``. ``NaN``
    entries are mapped to ``None`` so the dropout policy is uniform
    regardless of the source.
    """
    if isinstance(series, np.ndarray):
        out: list[float | None] = []
        for v in series.tolist():
            if v is None:
                out.append(None)
            elif isinstance(v, float) and not np.isfinite(v):
                out.append(None)
            else:
                out.append(float(v))
        return out

    out2: list[float | None] = []
    for v in series:  # type: ignore[union-attr]
        if v is None:
            out2.append(None)
        elif isinstance(v, float) and not np.isfinite(v):
            out2.append(None)
        else:
            out2.append(float(v))
    return out2


def _admit_axis(
    series: list[float | None],
    *,
    n_min: int,
    mosaic_threshold: float,
    saturation_tol: float,
) -> tuple[np.ndarray | None, str | None]:
    """Apply the dropout / saturation gates for a single axis.

    Returns ``(cleaned_array, None)`` on admission, ``(None, reason)``
    on exclusion. ``cleaned_array`` is the longest contiguous run of
    defined values, expressed as a ``np.ndarray[np.float64]``.
    """
    n_total = len(series)
    if n_total == 0:
        return None, "empty_series"

    n_defined = sum(1 for v in series if v is not None)

    if n_defined < mosaic_threshold * n_total:
        return None, (
            f"mosaic_dropout ({n_defined}/{n_total} below "
            f"{mosaic_threshold:.2f})"
        )

    start, end = _longest_contiguous_run(series)
    if start == -1:
        return None, "all_none"

    sub = series[start : end + 1]
    if len(sub) < n_min:
        return None, (
            f"too_short_after_dropout ({len(sub)} < n_min={n_min})"
        )

    arr = np.asarray(sub, dtype=np.float64)
    if float(np.std(arr)) < saturation_tol:
        return None, "saturated_axis"

    return arr, None


def granger_graph(
    source: GrangerGraphSource,
    *,
    axes: Iterable[str] | None = None,
    max_lag: int = DEFAULT_MAX_LAG,
    n_min: int = DEFAULT_N_MIN,
    saturation_tol: float = DEFAULT_SATURATION_TOL,
    mosaic_threshold: float = DEFAULT_MOSAIC_THRESHOLD,
) -> CausalCouplingGraph:
    """Build the directed Granger-causal coupling graph from a source.

    The function applies the protocol pre-registered in
    ``docs/COUPLING_DIAGNOSTICS.md``:

    1. Per-axis admission: drop empty series, series below the
       mosaic-coverage threshold, series whose longest contiguous
       run is shorter than ``n_min``, and saturated (zero-variance)
       series.
    2. Per-pair Granger: for every ordered pair of admitted axes,
       run :func:`autodynamics.coupling.granger.granger_coupling` on
       the longest contiguous runs.
    3. Aggregate: pairs whose F-stat could not be computed are
       recorded in ``null_pairs`` and excluded from downstream
       aggregates.

    Parameters
    ----------
    source:
        Either a :class:`autodynamics.ProfileTrajectory` or a mapping
        ``{axis_name: series}``. Series may contain ``None`` or
        ``NaN`` to encode missing measurements; the policy above is
        applied uniformly.
    axes:
        Optional explicit axis selection. When ``None``, all axes
        configured on the trajectory (or all keys of the mapping) are
        considered.
    max_lag:
        Maximum VAR lag for AIC selection. Default ``6``.
    n_min:
        Minimum admissible series length, applied both before and
        after the longest-contiguous-run extraction. Default ``50``.
    saturation_tol:
        Standard-deviation tolerance below which a series is treated
        as saturated.
    mosaic_threshold:
        Fraction of the original series that must be defined for the
        axis to be admitted.

    Returns
    -------
    CausalCouplingGraph
        The directed graph, with full bookkeeping of admitted axes,
        excluded axes (with reasons), and null pairs.
    """
    series_by_axis: dict[str, list[float | None]] = {}

    if isinstance(source, ProfileTrajectory):
        if axes is None:
            axes_to_use = source.axes
        else:
            axes_to_use = tuple(axes)
        for axis in axes_to_use:
            series_by_axis[axis] = list(source.axis_series(axis))
    else:
        if not hasattr(source, "items"):
            raise TypeError(
                "source must be a ProfileTrajectory or a Mapping; "
                f"got {type(source).__name__}"
            )
        if axes is None:
            axes_to_use = tuple(source.keys())  # type: ignore[union-attr]
        else:
            axes_to_use = tuple(axes)
        for axis in axes_to_use:
            if axis not in source:  # type: ignore[operator]
                series_by_axis[axis] = []
            else:
                series_by_axis[axis] = _series_to_floatlist(source[axis])  # type: ignore[index]

    cleaned: dict[str, np.ndarray] = {}
    excluded: dict[str, str] = {}
    axes_used: list[str] = []

    for axis in axes_to_use:
        series = series_by_axis[axis]
        arr, reason = _admit_axis(
            series,
            n_min=n_min,
            mosaic_threshold=mosaic_threshold,
            saturation_tol=saturation_tol,
        )
        if arr is None:
            excluded[axis] = reason or "unknown"
        else:
            cleaned[axis] = arr
            axes_used.append(axis)

    edges: dict[tuple[str, str], CausalCouplingResult] = {}
    null_pairs: list[tuple[str, str]] = []
    n_obs_seen: list[int] = []

    for a in axes_used:
        for b in axes_used:
            if a == b:
                continue
            res = granger_coupling(
                cleaned[a],
                cleaned[b],
                max_lag=max_lag,
                n_min=n_min,
            )
            edges[(a, b)] = res
            if res.f_stat is None:
                null_pairs.append((a, b))
            elif res.n_obs_used is not None:
                n_obs_seen.append(int(res.n_obs_used))

    n_obs_min = int(min(n_obs_seen)) if n_obs_seen else 0

    return CausalCouplingGraph(
        edges=edges,
        axes_used=tuple(axes_used),
        excluded_axes=excluded,
        null_pairs=tuple(null_pairs),
        n_obs_min=n_obs_min,
    )

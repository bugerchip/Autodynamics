"""CSV adapter for ``ProfileTrajectory``.

Loads a CSV whose columns include the canonical axis names
(``closure``, ``memory``, ``constraint``, ``persistence``,
``coherence``) and produces a :class:`ProfileTrajectory`. Missing
axis columns yield ``None`` for that axis on every snapshot. Empty
or whitespace-only cells are treated as ``None``. Extra columns are
ignored.

This adapter is intentionally minimal: no calibration, no
threshold tuning, no schema autodetection beyond the canonical
column names. Callers who need to translate alien column names
should rename the columns in their CSV before loading.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from pathlib import Path

from autonometrics import AutonomyProfile

from autodynamics.trajectory import ProfileTrajectory

# Canonical axis name -> internal field on AutonomyProfile.
# Mirrors ``autonometrics.profile._CANONICAL_TO_FIELD`` deliberately:
# we re-declare the mapping here to avoid coupling autodynamics to the
# private name of an Autonometrics module.
_AXIS_TO_PROFILE_FIELD: dict[str, str] = {
    "closure": "ratio_endo_total",
    "memory": "memory_endo_ratio",
    "constraint": "constraint_closure",
    "persistence": "rai_proxy_persistence",
    "coherence": "cba_theil_u",
}

_CANONICAL_AXES: tuple[str, ...] = tuple(_AXIS_TO_PROFILE_FIELD.keys())


def _parse_optional_float(value: str | None) -> float | None:
    """Coerce a CSV cell to ``float`` or ``None``.

    Empty strings and whitespace-only strings become ``None``;
    anything else is parsed as ``float`` (raises ``ValueError`` if the
    cell cannot be parsed). ``None`` itself maps to ``None``.
    """
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return float(stripped)


class CSVTrajectoryAdapter:
    """Build a :class:`ProfileTrajectory` from CSV input.

    Parameters
    ----------
    axes:
        Optional restriction passed to :class:`ProfileTrajectory`. When
        ``None`` (default) the resulting trajectory reports on all five
        canonical axes; passing an explicit subset bounds which axes
        the trajectory will surface, but does not change which columns
        the adapter reads from the CSV.
    order_column:
        Optional name of an integer-valued column to sort rows by
        before snapshots are appended (e.g. ``"step"``, ``"index"``,
        ``"seed"``). When ``None`` (default), the adapter preserves
        the row order found in the CSV.
    """

    def __init__(
        self,
        *,
        axes: Iterable[str] | None = None,
        order_column: str | None = None,
    ) -> None:
        self._axes = None if axes is None else tuple(axes)
        self._order_column = order_column

    def load_path(self, path: str | Path) -> ProfileTrajectory:
        """Load a CSV from a filesystem path."""
        with open(path, encoding="utf-8", newline="") as fh:
            return self.load_rows(csv.DictReader(fh))

    def load_rows(
        self, rows: Iterable[Mapping[str, str | None]]
    ) -> ProfileTrajectory:
        """Build a trajectory from an iterable of row mappings.

        Each row must be a mapping from column name to string value
        (the shape produced by :class:`csv.DictReader`). Rows are
        materialised eagerly so the adapter can sort by the optional
        ``order_column``.
        """
        materialised: list[Mapping[str, str | None]] = list(rows)
        if self._order_column is not None:
            materialised = sorted(
                materialised,
                key=lambda r: int(self._coerce_order_value(r)),
            )

        trajectory = ProfileTrajectory(axes=self._axes)
        for row in materialised:
            trajectory.append(self._row_to_profile(row))
        return trajectory

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _coerce_order_value(self, row: Mapping[str, str | None]) -> str:
        if self._order_column is None:  # pragma: no cover - guarded by caller
            raise RuntimeError("order_column not configured")
        if self._order_column not in row:
            raise KeyError(
                f"order_column {self._order_column!r} not found in row "
                f"with columns {sorted(row.keys())!r}"
            )
        value = row[self._order_column]
        if value is None or str(value).strip() == "":
            raise ValueError(
                f"order_column {self._order_column!r} is empty in a row; "
                "every row must have an integer ordinal when order_column is set"
            )
        return str(value)

    @staticmethod
    def _row_to_profile(
        row: Mapping[str, str | None],
    ) -> AutonomyProfile:
        kwargs: dict[str, float | None] = {}
        for axis, profile_field in _AXIS_TO_PROFILE_FIELD.items():
            kwargs[profile_field] = _parse_optional_float(row.get(axis))
        return AutonomyProfile(**kwargs)

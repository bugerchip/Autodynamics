"""Public reproducible example for Autodynamics v0.2.0a0.

Loads ``tests/fixtures/autonometrics_v0_8_sample.csv`` (a 15-row,
public, reproducible subset of the Autonometrics ``v0.8.0a0``
benchmark) and uses both adapters shipped in v0.2.0a0:

- :class:`CSVTrajectoryAdapter` to parse the CSV rows into autonomy
  profiles.
- :class:`BatchTrajectoryAdapter` to group the profiles by
  ``(class, params)`` and build one :class:`ProfileTrajectory` per
  group.

It then prints the per-axis :meth:`ProfileTrajectory.summary` for every
group and the cross-group :meth:`BatchTrajectoryAdapter.mean_summary`.

This script makes **no theoretical claims**. It is a sanity check that
the Autodynamics machinery can ingest publicly available autonomy
measurements and report standard descriptive statistics axis by axis.

Run::

    python examples/trajectory_demo.py
"""

from __future__ import annotations

import csv
from pathlib import Path

from autodynamics.adapters import (
    BatchTrajectoryAdapter,
    CSVTrajectoryAdapter,
)

_FIXTURE = (
    Path(__file__).resolve().parent.parent
    / "tests"
    / "fixtures"
    / "autonometrics_v0_8_sample.csv"
)
_AXES: tuple[str, ...] = (
    "closure",
    "memory",
    "constraint",
    "persistence",
    "coherence",
)
_METRICS: tuple[str, ...] = (
    "n_total",
    "n_defined",
    "mean",
    "std",
    "drift",
    "volatility",
    "path_length",
)


def _format_value(value: object) -> str:
    if value is None:
        return "    None"
    if isinstance(value, bool):
        return f"{value!s:>8}"
    if isinstance(value, int):
        return f"{value:>8d}"
    if isinstance(value, float):
        return f"{value:>8.4f}"
    return f"{value!s:>8}"


def _print_section_header(title: str) -> None:
    print()
    print(title)
    print("-" * max(len(title), 24))


def main() -> None:
    if not _FIXTURE.exists():  # pragma: no cover - guarded by repo layout
        raise SystemExit(
            f"fixture missing at {_FIXTURE}; run the test suite to "
            "regenerate or check tests/fixtures/README.md"
        )

    print(f"Loading {_FIXTURE.relative_to(Path(__file__).resolve().parent.parent)}")
    rows = list(csv.DictReader(_FIXTURE.open(encoding="utf-8")))
    print(f"Rows read: {len(rows)}")

    csv_adapter = CSVTrajectoryAdapter()
    batch = BatchTrajectoryAdapter()
    for row in rows:
        single = csv_adapter.load_rows([row])
        batch.add((row["class"], row["params"]), single[0].profile)

    trajectories = batch.trajectories()
    print(f"Groups built:  {len(trajectories)}")
    for key, traj in trajectories.items():
        print(f"  {key}: length={len(traj)}")

    for key, traj in trajectories.items():
        _print_section_header(f"Per-axis summary for {key}")
        summary = traj.summary()
        header = "  " + "axis".ljust(12) + "".join(
            f" {m:>8}" for m in _METRICS
        )
        print(header)
        print("  " + "-" * (len(header) - 2))
        for axis in _AXES:
            row = "  " + axis.ljust(12) + "".join(
                " " + _format_value(summary[axis][m]) for m in _METRICS
            )
            print(row)

    _print_section_header("Cross-group mean of summary metrics")
    mean_summary = batch.mean_summary()
    metrics_to_show = ("mean", "std", "drift", "volatility", "path_length")
    header = "  " + "axis".ljust(12) + "".join(
        f" {m:>10}" for m in metrics_to_show
    )
    print(header)
    print("  " + "-" * (len(header) - 2))
    for axis in _AXES:
        row = "  " + axis.ljust(12) + "".join(
            " " + _format_value(mean_summary[axis][m]).rjust(10)
            for m in metrics_to_show
        )
        print(row)


if __name__ == "__main__":
    main()

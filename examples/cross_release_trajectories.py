"""Cross-release trajectory infrastructure check (v0.2.0a0).

Loads every benchmark CSV published in
[`bugerchip/Autonometrics`](https://github.com/bugerchip/Autonometrics)
under ``docs/benchmarks/`` that ships canonical-axis columns,
constructs one :class:`ProfileTrajectory` per ``(class, params)`` group
per release, and reports the per-axis :meth:`ProfileTrajectory.summary`
plus a small aggregated table.

This is **infrastructure**, not validation. The script confirms that
the Autodynamics ``v0.2.0a0`` machinery can ingest the publicly
available Autonometrics datasets without errors. It makes **no**
predictive claim about dynamic regimes, attractors, transitions, or
correlation structure across releases.

Usage::

    python examples/cross_release_trajectories.py \
        --autonometrics-root ../Autonometrics \
        --out-dir docs/benchmarks

The default ``--autonometrics-root`` is ``../Autonometrics`` relative to
the script's parent (the Autodynamics repo root). Any release whose CSV
is not found is skipped with a logged note; the script does not abort.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

from autodynamics.adapters import (
    BatchTrajectoryAdapter,
    CSVTrajectoryAdapter,
)

# Autonometrics releases whose benchmarks declare canonical axis columns
# in CSV form. Listed in chronological order.
_RELEASES: tuple[str, ...] = (
    "v0.5.0a0",
    "v0.6.0a0",
    "v0.7.0a0",
    "v0.7.2a0",
    "v0.8.0a0",
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


class _Tee:
    """Mirror writes to several streams (stdout + a captured buffer)."""

    def __init__(self, *streams: object) -> None:
        self._streams = list(streams)

    def write(self, data: str) -> int:
        for stream in self._streams:
            stream.write(data)  # type: ignore[attr-defined]
        return len(data)

    def flush(self) -> None:
        for stream in self._streams:
            try:
                stream.flush()  # type: ignore[attr-defined]
            except AttributeError:  # pragma: no cover - best effort
                pass


def _format(value: object) -> str:
    if value is None:
        return "None"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _process_release(
    release: str, csv_path: Path
) -> tuple[BatchTrajectoryAdapter, list[dict[str, object]]]:
    """Build a batch from one release's CSV and return summary rows."""
    csv_adapter = CSVTrajectoryAdapter()
    batch = BatchTrajectoryAdapter()
    with csv_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = sorted(reader, key=lambda r: int(r.get("seed", "0") or "0"))
    for row in rows:
        single = csv_adapter.load_rows([row])
        key = (row.get("class", ""), row.get("params", ""))
        batch.add(key, single[0].profile)

    summary_rows: list[dict[str, object]] = []
    for key, traj in batch.trajectories().items():
        cls, params = key  # type: ignore[misc]
        per_axis = traj.summary()
        for axis in _AXES:
            entry = per_axis[axis]
            summary_rows.append(
                {
                    "release": release,
                    "class": cls,
                    "params": params,
                    "axis": axis,
                    **{metric: entry[metric] for metric in _METRICS},
                }
            )
    return batch, summary_rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cross_release_trajectories",
        description=__doc__,
    )
    default_anm_root = (
        Path(__file__).resolve().parent.parent.parent / "Autonometrics"
    )
    default_out_dir = (
        Path(__file__).resolve().parent.parent / "docs" / "benchmarks"
    )
    parser.add_argument(
        "--autonometrics-root",
        type=Path,
        default=default_anm_root,
        help=(
            "path to a local clone of bugerchip/Autonometrics. Default: "
            "sibling directory ../Autonometrics relative to this repo."
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=default_out_dir,
        help="directory to write the cross-release CSV and log into",
    )
    args = parser.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_out = args.out_dir / "cross_release_v0.2.0a0.csv"
    log_out = args.out_dir / "cross_release_v0.2.0a0.log.txt"

    log_buffer = io.StringIO()
    sys.stdout = _Tee(sys.__stdout__, log_buffer)

    print("=" * 78)
    print("Autodynamics v0.2.0a0 — cross-release infrastructure check")
    print("=" * 78)
    print(f"Autonometrics root: {args.autonometrics_root}")
    print(f"Output directory:   {args.out_dir}")
    print()

    summary_rows: list[dict[str, object]] = []
    bench_dir = args.autonometrics_root / "docs" / "benchmarks"

    for release in _RELEASES:
        csv_path = bench_dir / f"{release}.csv"
        if not csv_path.exists():
            print(f"[skip] {release}: not found at {csv_path}")
            continue
        print(f"[load] {release}: {csv_path}")
        try:
            batch, rows = _process_release(release, csv_path)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"[error] {release}: {exc!r}")
            continue
        summary_rows.extend(rows)
        print(f"        groups: {len(batch)}")
        for key in batch.group_keys:
            cls, params = key  # type: ignore[misc]
            length = len(batch.trajectories()[key])
            print(f"          - ({cls}, {params}) length={length}")

    if not summary_rows:
        print()
        print("No releases were processed. Aborting CSV write.")
        sys.stdout = sys.__stdout__
        log_out.write_text(log_buffer.getvalue(), encoding="utf-8")
        return 1

    print()
    print("Per-axis summary aggregated by (release, class, params, axis):")
    print("-" * 78)
    header_cols = ["release", "class", "params", "axis", *_METRICS]
    print(", ".join(header_cols))
    for row in summary_rows:
        print(", ".join(_format(row[c]) for c in header_cols))

    fieldnames = list(header_cols)
    with csv_out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary_rows:
            writer.writerow(
                {
                    key: ("" if row[key] is None else _format(row[key]))
                    for key in fieldnames
                }
            )

    print()
    print(f"Wrote {csv_out} ({len(summary_rows)} rows)")

    sys.stdout = sys.__stdout__
    log_out.write_text(log_buffer.getvalue(), encoding="utf-8")
    print(f"Wrote {log_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

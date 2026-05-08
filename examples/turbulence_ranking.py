"""Public validation experiment: turbulence ranking (v0.2.1a0).

Pre-registered design lives in
[`docs/TURBULENCE_RANKING.md`](../docs/TURBULENCE_RANKING.md). This
script is the executable counterpart: it loads the public Autonometrics
``v0.8.0a0`` benchmark, builds one :class:`ProfileTrajectory` per
``(class, params)`` group, computes per-class average volatility per
axis, and compares the resulting ordering against the pre-registered
ranking using Spearman rank correlation.

Usage::

    python examples/turbulence_ranking.py \
        --autonometrics-root ../Autonometrics \
        --out-dir docs/benchmarks

The script is the *only* place where LD-1..LD-3 (source dataset,
trajectory construction, aggregation rule) are operationalised. LD-4
(the pre-registered ranking) and LD-5 (the verification rule) live
inside this script as constants — changing them after the first run is
forbidden by the pre-registration discipline.
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

# ----------------------------------------------------------------------
# Pre-registered constants (LD-4, LD-5). DO NOT MODIFY AFTER FIRST RUN.
# ----------------------------------------------------------------------

# Pre-registered ranking by ascending cross-seed volatility.
# Rank 1 = least turbulent, rank 5 = most turbulent.
_PREREGISTERED_RANKING: dict[str, int] = {
    "PeriodicCycle": 1,
    "SimpleAutomaton": 2,
    "ECASystem": 3,
    "PromisedCycle": 4,
    "KauffmanNetwork": 5,
}

# LD-3 gate: a group must have at least this many defined values on
# an axis to contribute its volatility to the per-class average.
_MIN_DEFINED_PER_GROUP: int = 5

# LD-5 thresholds.
_PER_AXIS_RHO_PASS: float = 0.7
_REQUIRED_AXES_TO_PASS: int = 3
_EVALUABLE_AXES: tuple[str, ...] = (
    "closure",
    "memory",
    "constraint",
    "persistence",
)
_REPORT_AXES: tuple[str, ...] = (
    *_EVALUABLE_AXES,
    "coherence",
)

_SOURCE_RELEASE: str = "v0.8.0a0"


# ----------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------


class _Tee:
    """Mirror writes to several streams simultaneously."""

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
            except AttributeError:  # pragma: no cover
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


def _spearman_rho(observed: list[int], predicted: list[int]) -> float | None:
    """Spearman rank correlation between two integer rankings.

    Implemented as Pearson correlation on the rank values; this handles
    ties correctly when either input contains repeated ranks.
    """
    n = len(observed)
    if n < 2:
        return None
    mean_o = sum(observed) / n
    mean_p = sum(predicted) / n
    cov = sum(
        (o - mean_o) * (p - mean_p) for o, p in zip(observed, predicted)
    )
    var_o = sum((o - mean_o) ** 2 for o in observed)
    var_p = sum((p - mean_p) ** 2 for p in predicted)
    if var_o == 0.0 or var_p == 0.0:
        return None
    return cov / ((var_o * var_p) ** 0.5)


def _rank_with_ties(values: list[float]) -> list[float]:
    """Average-rank assignment with ties (1-indexed)."""
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while (
            j + 1 < len(indexed)
            and indexed[j + 1][1] == indexed[i][1]
        ):
            j += 1
        average = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = average
        i = j + 1
    return ranks


# ----------------------------------------------------------------------
# Core computation
# ----------------------------------------------------------------------


def _load_groups(
    csv_path: Path,
) -> dict[tuple[str, str], list[dict[str, str]]]:
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        groups.setdefault((row["class"], row["params"]), []).append(row)
    for key in groups:
        groups[key].sort(key=lambda r: int(r.get("seed", "0") or "0"))
    return groups


def _per_class_volatility(
    groups: dict[tuple[str, str], list[dict[str, str]]],
) -> dict[str, dict[str, float | None]]:
    """For each (class, axis), mean of group-level volatility over the
    qualifying groups (those with >= _MIN_DEFINED_PER_GROUP defined
    values on the axis)."""
    csv_adapter = CSVTrajectoryAdapter()
    per_class: dict[str, dict[str, list[float]]] = {}
    for (cls, params), rows in groups.items():
        traj = csv_adapter.load_rows(rows)
        summary = traj.summary()
        for axis in _REPORT_AXES:
            entry = summary[axis]
            n_defined = entry["n_defined"]
            if (
                not isinstance(n_defined, int)
                or n_defined < _MIN_DEFINED_PER_GROUP
            ):
                continue
            volatility = entry["volatility"]
            if volatility is None:
                continue
            per_class.setdefault(cls, {}).setdefault(axis, []).append(
                float(volatility)
            )

    out: dict[str, dict[str, float | None]] = {}
    for cls, axis_to_values in per_class.items():
        out[cls] = {}
        for axis in _REPORT_AXES:
            values = axis_to_values.get(axis, [])
            out[cls][axis] = (
                float(sum(values) / len(values)) if values else None
            )
    # Ensure every class appears even if no group qualified.
    for cls in _PREREGISTERED_RANKING:
        out.setdefault(cls, {axis: None for axis in _REPORT_AXES})
    return out


def _evaluate_axis(
    per_class: dict[str, dict[str, float | None]], axis: str
) -> tuple[list[tuple[str, float]], float | None]:
    """Return the observed (class, volatility) ranking ascending and the
    Spearman correlation against the pre-registered ranking restricted
    to the classes present."""
    pairs = [
        (cls, per_class[cls][axis])
        for cls in _PREREGISTERED_RANKING
        if per_class.get(cls, {}).get(axis) is not None
    ]
    pairs_sorted = sorted(
        pairs, key=lambda item: item[1]  # type: ignore[arg-type]
    )
    classes_present = [cls for cls, _ in pairs_sorted]
    if len(classes_present) < 3:
        return pairs_sorted, None
    observed_values = [v for _, v in pairs_sorted]
    observed_ranks = _rank_with_ties(observed_values)
    predicted_ranks = [
        float(_PREREGISTERED_RANKING[cls]) for cls in classes_present
    ]
    rho = _spearman_rho(
        [int(r * 2) for r in observed_ranks],
        [int(r * 2) for r in predicted_ranks],
    )
    return pairs_sorted, rho


# ----------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------


def _print_pre_registration_block() -> None:
    print("=" * 78)
    print(
        "Autodynamics — public validation experiment: turbulence ranking "
        "(v0.2.1a0)"
    )
    print("=" * 78)
    print(
        "Pre-registered design lives in docs/TURBULENCE_RANKING.md. "
        "This script's"
    )
    print(
        "constants (_PREREGISTERED_RANKING, _PER_AXIS_RHO_PASS, "
        "_REQUIRED_AXES_TO_PASS,"
    )
    print(
        "_MIN_DEFINED_PER_GROUP, _EVALUABLE_AXES) are the operational "
        "form of LD-4 and"
    )
    print("LD-5 and must not be modified after the first run.")
    print()
    print("Pre-registered ranking (rank 1 = least turbulent):")
    for cls, rank in sorted(
        _PREREGISTERED_RANKING.items(), key=lambda item: item[1]
    ):
        print(f"  {rank}. {cls}")
    print()
    print(f"Source release:    {_SOURCE_RELEASE}")
    print(f"Per-axis pass:     rho >= {_PER_AXIS_RHO_PASS}")
    print(
        f"Hypothesis pass:   pass in >= {_REQUIRED_AXES_TO_PASS} of "
        f"{len(_EVALUABLE_AXES)} evaluable axes ({list(_EVALUABLE_AXES)})"
    )
    print(
        f"Group qualifying:  n_defined per group >= {_MIN_DEFINED_PER_GROUP}"
    )
    print()


def _print_per_class_table(
    per_class: dict[str, dict[str, float | None]],
) -> None:
    print(
        "Per-class average volatility (mean over qualifying groups), axis "
        "by axis:"
    )
    print("-" * 78)
    header = "  " + "class".ljust(18) + "".join(
        f" {axis:>14}" for axis in _REPORT_AXES
    )
    print(header)
    print("  " + "-" * (len(header) - 2))
    for cls in sorted(_PREREGISTERED_RANKING):
        row = "  " + cls.ljust(18) + "".join(
            " " + _format(per_class.get(cls, {}).get(axis)).rjust(14)
            for axis in _REPORT_AXES
        )
        print(row)
    print()


def _print_per_axis_evaluation(
    per_class: dict[str, dict[str, float | None]],
) -> dict[str, dict[str, object]]:
    print(
        "Per-axis evaluation (observed ranking vs pre-registered, "
        "Spearman rho):"
    )
    print("-" * 78)
    results: dict[str, dict[str, object]] = {}
    for axis in _REPORT_AXES:
        pairs, rho = _evaluate_axis(per_class, axis)
        evaluable = axis in _EVALUABLE_AXES
        if not pairs:
            print(f"  {axis}: no qualifying groups")
            results[axis] = {
                "n_classes": 0,
                "rho": None,
                "passes": False,
                "evaluable": evaluable,
            }
            continue
        ordered = " < ".join(
            f"{cls}({_format(v)})" for cls, v in pairs
        )
        rho_str = "n/a" if rho is None else f"{rho:.4f}"
        passes = bool(
            evaluable and rho is not None and rho >= _PER_AXIS_RHO_PASS
        )
        verdict = (
            "PASS"
            if passes
            else ("REPORT-ONLY" if not evaluable else "FAIL")
        )
        print(
            f"  {axis}: rho={rho_str} [{verdict}] "
            f"observed: {ordered}"
        )
        results[axis] = {
            "n_classes": len(pairs),
            "rho": rho,
            "passes": passes,
            "evaluable": evaluable,
            "ordered": [cls for cls, _ in pairs],
        }
    print()
    return results


def _print_verdict(
    axis_results: dict[str, dict[str, object]],
) -> bool:
    n_passes = sum(
        1
        for axis in _EVALUABLE_AXES
        if bool(axis_results.get(axis, {}).get("passes"))
    )
    confirmed = n_passes >= _REQUIRED_AXES_TO_PASS
    print("Verdict")
    print("-" * 78)
    print(
        f"Evaluable axes that passed: {n_passes} / {len(_EVALUABLE_AXES)}"
    )
    print(
        f"Required to confirm:        {_REQUIRED_AXES_TO_PASS}"
    )
    if confirmed:
        print("Hypothesis: CONFIRMED")
    else:
        print("Hypothesis: REJECTED")
    print()
    return confirmed


def _write_csv(
    out_path: Path,
    per_class: dict[str, dict[str, float | None]],
    axis_results: dict[str, dict[str, object]],
) -> None:
    rows: list[dict[str, object]] = []
    for cls in sorted(_PREREGISTERED_RANKING):
        for axis in _REPORT_AXES:
            rows.append(
                {
                    "kind": "per_class_volatility",
                    "class": cls,
                    "axis": axis,
                    "value": per_class.get(cls, {}).get(axis),
                    "rho": "",
                    "passes": "",
                    "evaluable": "",
                }
            )
    for axis in _REPORT_AXES:
        result = axis_results.get(axis, {})
        rows.append(
            {
                "kind": "axis_evaluation",
                "class": "",
                "axis": axis,
                "value": result.get("n_classes"),
                "rho": result.get("rho"),
                "passes": result.get("passes"),
                "evaluable": result.get("evaluable"),
            }
        )
    fieldnames = list(rows[0].keys())
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {key: ("" if row[key] is None else _format(row[key]))
                 for key in fieldnames}
            )


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="turbulence_ranking",
        description=__doc__,
    )
    repo_root = Path(__file__).resolve().parent.parent
    parser.add_argument(
        "--autonometrics-root",
        type=Path,
        default=repo_root.parent / "Autonometrics",
        help=(
            "path to a local clone of bugerchip/Autonometrics. Default: "
            "sibling directory ../Autonometrics relative to this repo."
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=repo_root / "docs" / "benchmarks",
        help="directory to write the validation CSV and log into",
    )
    args = parser.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_out = args.out_dir / "turbulence_ranking_v0.2.1a0.csv"
    log_out = args.out_dir / "turbulence_ranking_v0.2.1a0.log.txt"

    log_buffer = io.StringIO()
    sys.stdout = _Tee(sys.__stdout__, log_buffer)

    _print_pre_registration_block()

    csv_path = (
        args.autonometrics_root
        / "docs"
        / "benchmarks"
        / f"{_SOURCE_RELEASE}.csv"
    )
    if not csv_path.exists():
        print(f"[error] source CSV not found at {csv_path}")
        sys.stdout = sys.__stdout__
        log_out.write_text(log_buffer.getvalue(), encoding="utf-8")
        return 1

    print(f"[load] {csv_path}")
    groups = _load_groups(csv_path)
    print(f"        groups: {len(groups)}")

    # PO-2 reporting (transparent up-front before evaluation).
    print()

    # Use BatchTrajectoryAdapter as a sanity check that the adapter
    # pipeline accepts every group; this is also redundant evidence for
    # PO-1.
    csv_adapter = CSVTrajectoryAdapter()
    batch = BatchTrajectoryAdapter()
    for key, rows in groups.items():
        per_group_traj = csv_adapter.load_rows(rows)
        for snap in per_group_traj:
            batch.add(key, snap.profile)
    materialised = batch.trajectories()
    print(f"[batch] materialised {len(materialised)} trajectories")
    print()

    per_class = _per_class_volatility(groups)
    _print_per_class_table(per_class)

    axis_results = _print_per_axis_evaluation(per_class)

    confirmed = _print_verdict(axis_results)

    _write_csv(csv_out, per_class, axis_results)
    print(f"Wrote {csv_out}")

    sys.stdout = sys.__stdout__
    log_out.write_text(log_buffer.getvalue(), encoding="utf-8")
    print(f"Wrote {log_out}")
    return 0 if confirmed else 2


if __name__ == "__main__":
    raise SystemExit(main())

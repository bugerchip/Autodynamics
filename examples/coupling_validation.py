"""Public validation experiment: Granger coupling on the public zoo (v0.3.0a0).

Pre-registered design lives in
[`docs/COUPLING_VALIDATION.md`](../docs/COUPLING_VALIDATION.md). This
script is the executable counterpart: it loads the public Autonometrics
``v0.8.0a0`` benchmark, builds one :class:`ProfileTrajectory` per
``(class, params)`` group, runs :func:`granger_graph` against every
group with the LD-3 relaxed configuration, and reports per-group
admission and edge statistics plus the aggregate verdict against
PO-1, PO-2 and PO-3.

Usage::

    python examples/coupling_validation.py \
        --autonometrics-root ../Autonometrics \
        --out-dir docs/benchmarks

The script is the *only* place where LD-1..LD-4 (source dataset,
trajectory construction, coupling configuration, per-group output)
are operationalised. LD-5 (the verification rule) lives inside this
script as constants — changing them after the first run is forbidden
by the pre-registration discipline.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

from autodynamics.adapters import CSVTrajectoryAdapter
from autodynamics.coupling import density, granger_graph, symmetry_ratio


# ----------------------------------------------------------------------
# Pre-registered constants (LD-3, LD-5). DO NOT MODIFY AFTER FIRST RUN.
# ----------------------------------------------------------------------

_SOURCE_RELEASE: str = "v0.8.0a0"

_N_MIN: int = 10
_MAX_LAG: int = 2
_MOSAIC_THRESHOLD: float = 0.5
_SATURATION_TOL: float = 1e-12

_AXES: tuple[str, ...] = (
    "closure",
    "memory",
    "constraint",
    "persistence",
    "coherence",
)

# LD-5 thresholds.
_PO2_MIN_GROUPS_WITH_TWO_AXES_FRACTION: float = 0.50
_PO3_MIN_FINITE_EDGES_FRACTION: float = 0.30
_ALPHA: float = 0.05


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


def _summarise_group(
    cls: str,
    params: str,
    rows: list[dict[str, str]],
) -> dict[str, object]:
    csv_adapter = CSVTrajectoryAdapter()
    traj = csv_adapter.load_rows(rows)
    graph = granger_graph(
        traj,
        max_lag=_MAX_LAG,
        n_min=_N_MIN,
        mosaic_threshold=_MOSAIC_THRESHOLD,
        saturation_tol=_SATURATION_TOL,
    )
    n_axes_admitted = len(graph.axes_used)
    n_edges = len(graph.edges)
    finite_edges = [
        result for result in graph.edges.values()
        if result.f_stat is not None
    ]
    n_finite = len(finite_edges)
    n_significant = sum(
        1
        for result in finite_edges
        if result.p_value is not None and result.p_value < _ALPHA
    )
    sym = symmetry_ratio(graph)
    dens = density(graph)
    excluded = ";".join(
        f"{ax}:{reason}" for ax, reason in sorted(graph.excluded_axes.items())
    )
    return {
        "class": cls,
        "params": params,
        "trajectory_length": len(traj),
        "axes_admitted": n_axes_admitted,
        "axes_used": ",".join(graph.axes_used),
        "edges": n_edges,
        "edges_finite": n_finite,
        "edges_significant_p_lt_05": n_significant,
        "symmetry_ratio": sym,
        "density": dens,
        "excluded": excluded,
    }


# ----------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------


def _print_pre_registration_block() -> None:
    print("=" * 78)
    print(
        "Autodynamics — public validation experiment: Granger coupling "
        "(v0.3.0a0)"
    )
    print("=" * 78)
    print(
        "Pre-registered design lives in docs/COUPLING_VALIDATION.md. This "
        "script's"
    )
    print(
        "constants (_N_MIN, _MAX_LAG, _MOSAIC_THRESHOLD, _SATURATION_TOL, "
        "_AXES,"
    )
    print(
        "_PO2_MIN_GROUPS_WITH_TWO_AXES_FRACTION, "
        "_PO3_MIN_FINITE_EDGES_FRACTION) are the"
    )
    print(
        "operational form of LD-3 and LD-5 and must not be modified after "
        "the first run."
    )
    print()
    print(f"Source release:           {_SOURCE_RELEASE}")
    print(f"Coupling n_min:           {_N_MIN}")
    print(f"Coupling max_lag:         {_MAX_LAG}")
    print(f"Mosaic threshold:         {_MOSAIC_THRESHOLD}")
    print(f"Saturation tolerance:     {_SATURATION_TOL}")
    print(f"Significance alpha:       {_ALPHA}")
    print(
        f"PO-2 threshold:           >= "
        f"{_PO2_MIN_GROUPS_WITH_TWO_AXES_FRACTION:.0%} of groups have "
        ">=2 admitted axes"
    )
    print(
        f"PO-3 threshold:           >= "
        f"{_PO3_MIN_FINITE_EDGES_FRACTION:.0%} of admitted edges have "
        "finite f_stat"
    )
    print()


def _print_per_group_table(rows: list[dict[str, object]]) -> None:
    print("Per-group coupling output:")
    print("-" * 78)
    header_fields = [
        ("class", 18),
        ("params", 22),
        ("len", 5),
        ("ax", 3),
        ("ed", 3),
        ("ed_fin", 7),
        ("ed_sig", 7),
        ("sym", 8),
        ("dens", 8),
    ]
    header = "  " + " ".join(name.ljust(width) for name, width in header_fields)
    print(header)
    print("  " + "-" * (len(header) - 2))
    for row in rows:
        cells = [
            str(row["class"])[:18].ljust(18),
            str(row["params"])[:22].ljust(22),
            str(row["trajectory_length"]).ljust(5),
            str(row["axes_admitted"]).ljust(3),
            str(row["edges"]).ljust(3),
            str(row["edges_finite"]).ljust(7),
            str(row["edges_significant_p_lt_05"]).ljust(7),
            _format(row["symmetry_ratio"])[:8].ljust(8),
            _format(row["density"])[:8].ljust(8),
        ]
        print("  " + " ".join(cells))
    print()


def _print_aggregate(rows: list[dict[str, object]]) -> dict[str, object]:
    n_groups = len(rows)
    n_with_two_axes = sum(
        1 for r in rows if int(r["axes_admitted"]) >= 2  # type: ignore[arg-type]
    )
    total_edges = sum(int(r["edges"]) for r in rows)  # type: ignore[arg-type]
    total_finite = sum(
        int(r["edges_finite"]) for r in rows  # type: ignore[arg-type]
    )
    total_sig = sum(
        int(r["edges_significant_p_lt_05"]) for r in rows  # type: ignore[arg-type]
    )
    frac_two_axes = (
        n_with_two_axes / n_groups if n_groups > 0 else 0.0
    )
    frac_finite = (
        total_finite / total_edges if total_edges > 0 else 0.0
    )
    print("Aggregate")
    print("-" * 78)
    print(f"  groups total:                  {n_groups}")
    print(
        f"  groups with >= 2 admitted axes: {n_with_two_axes}"
        f"  ({frac_two_axes:.2%})"
    )
    print(f"  edges total (admitted):        {total_edges}")
    print(
        f"  edges with finite f_stat:      {total_finite}"
        f"  ({frac_finite:.2%})"
    )
    print(
        f"  edges significant (p < {_ALPHA}):    {total_sig}"
    )
    print()
    return {
        "n_groups": n_groups,
        "n_with_two_axes": n_with_two_axes,
        "frac_two_axes": frac_two_axes,
        "total_edges": total_edges,
        "total_finite": total_finite,
        "total_significant": total_sig,
        "frac_finite": frac_finite,
    }


def _print_verdict(aggregate: dict[str, object]) -> bool:
    print("Verdict")
    print("-" * 78)
    po1_pass = True  # by construction (we got here without raising)
    po2_pass = (
        float(aggregate["frac_two_axes"])  # type: ignore[arg-type]
        >= _PO2_MIN_GROUPS_WITH_TWO_AXES_FRACTION
    )
    po3_pass = (
        float(aggregate["frac_finite"])  # type: ignore[arg-type]
        >= _PO3_MIN_FINITE_EDGES_FRACTION
    )
    print(f"  PO-1 (script runs):              {'PASS' if po1_pass else 'FAIL'}")
    print(
        f"  PO-2 (>= {_PO2_MIN_GROUPS_WITH_TWO_AXES_FRACTION:.0%} groups "
        f"with >=2 axes): "
        f"{'PASS' if po2_pass else 'FAIL'} "
        f"({aggregate['frac_two_axes']:.2%})"  # type: ignore[str-format]
    )
    print(
        f"  PO-3 (>= {_PO3_MIN_FINITE_EDGES_FRACTION:.0%} of edges finite): "
        f"{'PASS' if po3_pass else 'FAIL'} "
        f"({aggregate['frac_finite']:.2%})"  # type: ignore[str-format]
    )
    confirmed = po1_pass and po2_pass and po3_pass
    print()
    print(f"  Hypothesis: {'CONFIRMED' if confirmed else 'REJECTED'}")
    print()
    return confirmed


def _write_csv(
    out_path: Path,
    rows: list[dict[str, object]],
    aggregate: dict[str, object],
) -> None:
    fieldnames_groups = [
        "kind",
        "class",
        "params",
        "trajectory_length",
        "axes_admitted",
        "axes_used",
        "edges",
        "edges_finite",
        "edges_significant_p_lt_05",
        "symmetry_ratio",
        "density",
        "excluded",
    ]
    fieldnames_aggregate = ["kind", "metric", "value"]
    fieldnames = sorted(
        set(fieldnames_groups + fieldnames_aggregate),
        key=lambda x: (
            (fieldnames_groups + fieldnames_aggregate).index(x)
        ),
    )
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out: dict[str, object] = {key: "" for key in fieldnames}
            out["kind"] = "per_group_coupling"
            for key in fieldnames_groups:
                if key in row and key != "kind":
                    out[key] = (
                        "" if row[key] is None else _format(row[key])
                    )
            writer.writerow(out)
        for key in (
            "n_groups",
            "n_with_two_axes",
            "frac_two_axes",
            "total_edges",
            "total_finite",
            "total_significant",
            "frac_finite",
        ):
            out = {field: "" for field in fieldnames}
            out["kind"] = "aggregate"
            out["metric"] = key
            out["value"] = _format(aggregate[key])
            writer.writerow(out)


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="coupling_validation",
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
    csv_out = args.out_dir / "coupling_v0.3.0a0.csv"
    log_out = args.out_dir / "coupling_v0.3.0a0.log.txt"

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
    print()

    rows: list[dict[str, object]] = []
    for (cls, params), group_rows in sorted(groups.items()):
        rows.append(_summarise_group(cls, params, group_rows))

    _print_per_group_table(rows)
    aggregate = _print_aggregate(rows)
    confirmed = _print_verdict(aggregate)

    _write_csv(csv_out, rows, aggregate)
    print(f"Wrote {csv_out}")

    sys.stdout = sys.__stdout__
    log_out.write_text(log_buffer.getvalue(), encoding="utf-8")
    print(f"Wrote {log_out}")
    return 0 if confirmed else 2


if __name__ == "__main__":
    raise SystemExit(main())

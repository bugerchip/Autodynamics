"""Public validation experiment: envelope generalisation (v0.4.0a0).

Pre-registered design lives in
[`docs/ENVELOPE_VALIDATION.md`](../docs/ENVELOPE_VALIDATION.md). This
script is the executable counterpart: it loads the public Autonometrics
``v0.8.0a0`` benchmark, splits each ``(class, params)`` group's seeds
into a 70 / 30 train / test split, learns an :class:`Envelope` from
the train subset using the cycle defaults, evaluates it against every
profile of the test subset, and reports per-group + aggregated
containment statistics plus the verdict against PO-1, PO-2 and PO-3.

Usage::

    python examples/envelope_validation.py \
        --autonometrics-root ../Autonometrics \
        --out-dir docs/benchmarks

The script is the *only* place where LD-1..LD-4 (source dataset,
train/test split, envelope construction, per-group output) are
operationalised. LD-5 (the verification rule) lives inside this
script as constants — changing them after the first run is forbidden
by the pre-registration discipline.
"""

from __future__ import annotations

import argparse
import csv
import io
import math
import sys
from pathlib import Path

from autodynamics import (
    CSVTrajectoryAdapter,
    ContainmentVerdict,
    Envelope,
    ProfileTrajectory,
)


# ----------------------------------------------------------------------
# Pre-registered constants (LD-3, LD-5). DO NOT MODIFY AFTER FIRST RUN.
# ----------------------------------------------------------------------

_SOURCE_RELEASE: str = "v0.8.0a0"

_TRAIN_FRACTION: float = 0.7
_WIDTH_MULTIPLIER: float = 2.0

_AXES: tuple[str, ...] = (
    "closure",
    "memory",
    "constraint",
    "persistence",
    "coherence",
)

# LD-5 thresholds.
_PO2_MIN_NOT_OUTSIDE_FRACTION: float = 0.70
_PO3_MIN_INSIDE_FRACTION: float = 0.40


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


def _split_rows(
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    n = len(rows)
    n_train = max(1, math.ceil(_TRAIN_FRACTION * n))
    if n_train >= n:
        # group too small to provide a non-empty test set
        return rows, []
    return rows[:n_train], rows[n_train:]


def _summarise_group(
    cls: str,
    params: str,
    rows: list[dict[str, str]],
) -> dict[str, object]:
    csv_adapter = CSVTrajectoryAdapter()
    train_rows, test_rows = _split_rows(rows)
    train_traj = csv_adapter.load_rows(train_rows)
    if not test_rows:
        return {
            "class": cls,
            "params": params,
            "n_train": len(train_traj),
            "n_test": 0,
            "axes_admitted": "",
            "trivial": True,
            "test_inside": 0,
            "test_outside": 0,
            "test_undefined": 0,
        }

    envelope = Envelope.from_trajectory(
        train_traj,
        width_multiplier=_WIDTH_MULTIPLIER,
        axes=None,
    )
    is_trivial = len(envelope) == 0

    test_traj: ProfileTrajectory = csv_adapter.load_rows(test_rows)

    inside = 0
    outside = 0
    undefined = 0
    for snap in test_traj:
        verdict = envelope.evaluate(snap.profile).verdict
        if verdict == ContainmentVerdict.INSIDE:
            inside += 1
        elif verdict == ContainmentVerdict.OUTSIDE:
            outside += 1
        else:
            undefined += 1

    return {
        "class": cls,
        "params": params,
        "n_train": len(train_traj),
        "n_test": len(test_traj),
        "axes_admitted": ",".join(envelope.axes),
        "trivial": is_trivial,
        "test_inside": inside,
        "test_outside": outside,
        "test_undefined": undefined,
    }


# ----------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------


def _print_pre_registration_block() -> None:
    print("=" * 78)
    print(
        "Autodynamics — public validation experiment: envelope "
        "generalisation (v0.4.0a0)"
    )
    print("=" * 78)
    print(
        "Pre-registered design lives in docs/ENVELOPE_VALIDATION.md. "
        "This script's"
    )
    print(
        "constants (_TRAIN_FRACTION, _WIDTH_MULTIPLIER, "
        "_PO2_MIN_NOT_OUTSIDE_FRACTION,"
    )
    print(
        "_PO3_MIN_INSIDE_FRACTION) are the operational form of LD-3 and "
        "LD-5 and"
    )
    print("must not be modified after the first run.")
    print()
    print(f"Source release:          {_SOURCE_RELEASE}")
    print(f"Train fraction:          {_TRAIN_FRACTION}")
    print(f"Width multiplier:        {_WIDTH_MULTIPLIER}")
    print(
        f"PO-2 threshold (NOT OUT): >= {_PO2_MIN_NOT_OUTSIDE_FRACTION:.0%}"
    )
    print(
        f"PO-3 threshold (INSIDE):  >= {_PO3_MIN_INSIDE_FRACTION:.0%}"
    )
    print()


def _print_per_group_table(rows: list[dict[str, object]]) -> None:
    print("Per-group containment output:")
    print("-" * 78)
    header_fields = [
        ("class", 18),
        ("params", 22),
        ("ntr", 4),
        ("nte", 4),
        ("ax", 3),
        ("in", 4),
        ("out", 4),
        ("und", 4),
        ("triv", 5),
    ]
    header = "  " + " ".join(name.ljust(width) for name, width in header_fields)
    print(header)
    print("  " + "-" * (len(header) - 2))
    for row in rows:
        cells = [
            str(row["class"])[:18].ljust(18),
            str(row["params"])[:22].ljust(22),
            str(row["n_train"]).ljust(4),
            str(row["n_test"]).ljust(4),
            str(len(str(row["axes_admitted"]).split(","))
                if row["axes_admitted"] else 0).ljust(3),
            str(row["test_inside"]).ljust(4),
            str(row["test_outside"]).ljust(4),
            str(row["test_undefined"]).ljust(4),
            ("yes" if row["trivial"] else "no").ljust(5),
        ]
        print("  " + " ".join(cells))
    print()


def _print_aggregate(rows: list[dict[str, object]]) -> dict[str, object]:
    n_groups = len(rows)
    n_trivial = sum(1 for r in rows if bool(r["trivial"]))
    n_unsplit = sum(1 for r in rows if int(r["n_test"]) == 0)  # type: ignore[arg-type]
    nontrivial = [
        r for r in rows
        if not bool(r["trivial"]) and int(r["n_test"]) > 0  # type: ignore[arg-type]
    ]
    nt_inside = sum(int(r["test_inside"]) for r in nontrivial)  # type: ignore[arg-type]
    nt_outside = sum(int(r["test_outside"]) for r in nontrivial)  # type: ignore[arg-type]
    nt_undefined = sum(int(r["test_undefined"]) for r in nontrivial)  # type: ignore[arg-type]
    nt_total = nt_inside + nt_outside + nt_undefined
    frac_not_outside = (
        (nt_inside + nt_undefined) / nt_total if nt_total > 0 else 0.0
    )
    frac_inside = nt_inside / nt_total if nt_total > 0 else 0.0
    print("Aggregate")
    print("-" * 78)
    print(f"  groups total:                  {n_groups}")
    print(f"  groups trivial (empty env):    {n_trivial}")
    print(f"  groups unsplit (n_seeds==1):   {n_unsplit}")
    print(f"  non-trivial groups:            {len(nontrivial)}")
    print(f"  test profiles (non-trivial):   {nt_total}")
    print(f"    INSIDE:                      {nt_inside}")
    print(f"    OUTSIDE:                     {nt_outside}")
    print(f"    UNDEFINED:                   {nt_undefined}")
    print(
        f"  fraction NOT OUTSIDE:          {frac_not_outside:.2%}"
    )
    print(
        f"  fraction INSIDE:               {frac_inside:.2%}"
    )
    print()
    return {
        "n_groups": n_groups,
        "n_trivial": n_trivial,
        "n_unsplit": n_unsplit,
        "n_nontrivial_groups": len(nontrivial),
        "nt_total": nt_total,
        "nt_inside": nt_inside,
        "nt_outside": nt_outside,
        "nt_undefined": nt_undefined,
        "frac_not_outside": frac_not_outside,
        "frac_inside": frac_inside,
    }


def _print_verdict(aggregate: dict[str, object]) -> bool:
    print("Verdict")
    print("-" * 78)
    po1_pass = True
    po2_pass = (
        float(aggregate["frac_not_outside"])  # type: ignore[arg-type]
        >= _PO2_MIN_NOT_OUTSIDE_FRACTION
    )
    po3_pass = (
        float(aggregate["frac_inside"])  # type: ignore[arg-type]
        >= _PO3_MIN_INSIDE_FRACTION
    )
    print(f"  PO-1 (script runs):                  {'PASS' if po1_pass else 'FAIL'}")
    print(
        f"  PO-2 (>= {_PO2_MIN_NOT_OUTSIDE_FRACTION:.0%} NOT OUTSIDE): "
        f"{'PASS' if po2_pass else 'FAIL'} "
        f"({aggregate['frac_not_outside']:.2%})"  # type: ignore[str-format]
    )
    print(
        f"  PO-3 (>= {_PO3_MIN_INSIDE_FRACTION:.0%} INSIDE):       "
        f"{'PASS' if po3_pass else 'FAIL'} "
        f"({aggregate['frac_inside']:.2%})"  # type: ignore[str-format]
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
        "n_train",
        "n_test",
        "axes_admitted",
        "trivial",
        "test_inside",
        "test_outside",
        "test_undefined",
    ]
    fieldnames_aggregate = ["kind", "metric", "value"]
    fieldnames = []
    for fld in fieldnames_groups + fieldnames_aggregate:
        if fld not in fieldnames:
            fieldnames.append(fld)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out: dict[str, object] = {key: "" for key in fieldnames}
            out["kind"] = "per_group_envelope"
            for key in fieldnames_groups:
                if key in row and key != "kind":
                    out[key] = (
                        "" if row[key] is None else _format(row[key])
                    )
            writer.writerow(out)
        for key in (
            "n_groups",
            "n_trivial",
            "n_unsplit",
            "n_nontrivial_groups",
            "nt_total",
            "nt_inside",
            "nt_outside",
            "nt_undefined",
            "frac_not_outside",
            "frac_inside",
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
        prog="envelope_validation",
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
    csv_out = args.out_dir / "envelope_v0.4.0a0.csv"
    log_out = args.out_dir / "envelope_v0.4.0a0.log.txt"

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

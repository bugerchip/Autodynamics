"""Pre-registration tests for ``docs/TRAJECTORY_DIAGNOSTICS.md`` (v0.2.0a0).

Each test maps to one of the predicted outcomes (PO-1 .. PO-4) of the
pre-registration document. A test failure means the cycle's verdict is
not positive and the implementation must be revisited before the
release ships.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest
from autonometrics import AutonomyProfile

from autodynamics import ProfileTrajectory

# ----------------------------------------------------------------------
# Fixture loader (inline; the CSVTrajectoryAdapter ships in v0.2.x
# Block C and will replace this helper in a follow-up PR).
# ----------------------------------------------------------------------

_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "autonometrics_v0_8_sample.csv"
)
_SATURATION_TOL = 1e-12


def _parse_optional_float(value: str | None) -> float | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return float(stripped)


def _row_to_profile(row: dict[str, str]) -> AutonomyProfile:
    return AutonomyProfile(
        ratio_endo_total=_parse_optional_float(row.get("closure")),
        memory_endo_ratio=_parse_optional_float(row.get("memory")),
        constraint_closure=_parse_optional_float(row.get("constraint")),
        rai_proxy_persistence=_parse_optional_float(row.get("persistence")),
        cba_theil_u=_parse_optional_float(row.get("coherence")),
    )


def _load_grouped_trajectories(
    csv_path: Path,
) -> dict[tuple[str, str], ProfileTrajectory]:
    rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        key = (row["class"], row["params"])
        grouped.setdefault(key, []).append(row)
    trajectories: dict[tuple[str, str], ProfileTrajectory] = {}
    for key, group_rows in grouped.items():
        group_rows.sort(key=lambda r: int(r["seed"]))
        traj = ProfileTrajectory()
        for row in group_rows:
            traj.append(_row_to_profile(row))
        trajectories[key] = traj
    return trajectories


# ----------------------------------------------------------------------
# PO-1 — Saturation theorem (LD-1)
# ----------------------------------------------------------------------


def _saturated_trajectory(
    *, length: int, closure: float | None = None
) -> ProfileTrajectory:
    traj = ProfileTrajectory(axes=("closure",))
    for _ in range(length):
        traj.append(AutonomyProfile(ratio_endo_total=closure))
    return traj


@pytest.mark.parametrize(
    "value", [0.0, 0.5, 1.0]
)
def test_po1_saturation_theorem_velocities_are_zero(value: float) -> None:
    traj = _saturated_trajectory(length=8, closure=value)
    velocities = traj.velocities("closure")
    assert len(velocities) == 7
    for v in velocities:
        assert v is not None
        assert abs(v) < _SATURATION_TOL


@pytest.mark.parametrize("value", [0.0, 0.5, 1.0])
def test_po1_saturation_theorem_path_length_is_zero(value: float) -> None:
    traj = _saturated_trajectory(length=8, closure=value)
    pl = traj.path_length_per_axis()["closure"]
    assert pl is not None
    assert abs(pl) < _SATURATION_TOL


@pytest.mark.parametrize("value", [0.0, 0.5, 1.0])
def test_po1_saturation_theorem_volatility_is_zero(value: float) -> None:
    traj = _saturated_trajectory(length=8, closure=value)
    vol = traj.volatility("closure")
    assert vol is not None
    assert abs(vol) < _SATURATION_TOL


@pytest.mark.parametrize("value", [0.0, 0.5, 1.0])
def test_po1_saturation_theorem_drift_is_zero(value: float) -> None:
    traj = _saturated_trajectory(length=8, closure=value)
    drift = traj.drift("closure")
    assert drift is not None
    assert abs(drift) < _SATURATION_TOL


def test_po1_saturation_theorem_holds_across_all_canonical_axes() -> None:
    """LD-1 specialises to every axis configured on the trajectory: a
    fully saturated profile (every axis identical across snapshots) must
    yield zero drift, volatility and path_length on every axis."""
    profile = AutonomyProfile(
        ratio_endo_total=0.7,
        memory_endo_ratio=0.4,
        constraint_closure=0.9,
        rai_proxy_persistence=0.2,
        cba_theil_u=0.6,
    )
    traj = ProfileTrajectory()
    for _ in range(6):
        traj.append(profile)
    summary = traj.summary()
    for axis in (
        "closure",
        "memory",
        "constraint",
        "persistence",
        "coherence",
    ):
        for metric in ("drift", "volatility", "path_length"):
            value = summary[axis][metric]
            assert value is not None, f"{axis}.{metric} unexpectedly None"
            assert abs(value) < _SATURATION_TOL, (
                f"{axis}.{metric} = {value!r} exceeds saturation tolerance"
            )


# ----------------------------------------------------------------------
# PO-2 — Named boundary regimes (LD-2)
# ----------------------------------------------------------------------


def test_po2_empty_regime_dynamic_metrics_are_none() -> None:
    traj = ProfileTrajectory(axes=("closure",))
    assert traj.velocities("closure") == []
    assert traj.accelerations("closure") == []
    assert traj.drift("closure") is None
    assert traj.volatility("closure") is None
    assert traj.path_length_per_axis()["closure"] is None
    summary = traj.summary()
    assert summary["closure"]["n_total"] == 0
    assert summary["closure"]["n_defined"] == 0
    for metric in ("mean", "std", "drift", "volatility", "path_length"):
        assert summary["closure"][metric] is None


def test_po2_single_snapshot_regime_dynamic_metrics_are_none() -> None:
    traj = ProfileTrajectory(axes=("closure",))
    traj.append(AutonomyProfile(ratio_endo_total=0.4))
    assert traj.velocities("closure") == []
    assert traj.drift("closure") is None
    assert traj.volatility("closure") is None
    assert traj.path_length_per_axis()["closure"] is None
    summary = traj.summary()
    assert summary["closure"]["n_total"] == 1
    assert summary["closure"]["n_defined"] == 1
    assert summary["closure"]["mean"] == pytest.approx(0.4)
    assert summary["closure"]["std"] is None


def test_po2_undefined_axis_regime_yields_none_for_every_metric() -> None:
    traj = ProfileTrajectory(axes=("closure",))
    for _ in range(5):
        traj.append(AutonomyProfile(ratio_endo_total=None))
    summary = traj.summary()
    assert summary["closure"]["n_total"] == 5
    assert summary["closure"]["n_defined"] == 0
    for metric in ("mean", "std", "drift", "volatility", "path_length"):
        assert summary["closure"][metric] is None


def test_po2_saturated_axis_regime_specialises_ld1() -> None:
    traj = _saturated_trajectory(length=4, closure=0.5)
    summary = traj.summary()["closure"]
    assert summary["drift"] == pytest.approx(0.0)
    assert summary["volatility"] == pytest.approx(0.0)
    assert summary["path_length"] == pytest.approx(0.0)
    assert summary["std"] == pytest.approx(0.0)
    assert summary["mean"] == pytest.approx(0.5)


def test_po2_mosaic_degraded_regime_reports_partial_n_defined() -> None:
    traj = ProfileTrajectory(axes=("closure",))
    for v in [0.1, None, 0.4, None, 0.7]:
        traj.append(AutonomyProfile(ratio_endo_total=v))
    summary = traj.summary()["closure"]
    assert summary["n_total"] == 5
    assert summary["n_defined"] == 3
    # drift skips internal Nones: 0.7 - 0.1 = 0.6
    assert summary["drift"] == pytest.approx(0.6)
    assert summary["mean"] == pytest.approx(0.4)
    # path_length skips Nones in velocities; defined velocities are
    # those whose endpoints are both defined, none here, so the metric
    # is None.
    assert summary["path_length"] is None


def test_po2_rolling_window_contract_is_trailing() -> None:
    """LD-3 — emit None until the window first fits (i >= window - 1)."""
    traj = ProfileTrajectory(axes=("closure",))
    for v in [0.0, 1.0, 2.0, 3.0]:
        traj.append(AutonomyProfile(ratio_endo_total=v))
    rm = traj.rolling_mean("closure", window=2)
    assert rm[0] is None
    assert rm[1] == pytest.approx(0.5)
    assert rm[2] == pytest.approx(1.5)
    assert rm[3] == pytest.approx(2.5)


# ----------------------------------------------------------------------
# PO-3 — CSV ingestion is total
# ----------------------------------------------------------------------


def test_po3_fixture_file_exists() -> None:
    assert _FIXTURE_PATH.exists(), (
        "expected fixture missing: "
        f"{_FIXTURE_PATH} — see tests/fixtures/README.md to regenerate"
    )


def test_po3_loader_yields_three_groups_of_five_snapshots() -> None:
    trajectories = _load_grouped_trajectories(_FIXTURE_PATH)
    assert set(trajectories.keys()) == {
        ("ECASystem", "rule=30"),
        ("KauffmanNetwork", "coupling=0.5"),
        ("PeriodicCycle", "period=2"),
    }
    for key, traj in trajectories.items():
        assert len(traj) == 5, f"group {key} has unexpected length"


def test_po3_summary_runs_on_every_group_without_errors() -> None:
    trajectories = _load_grouped_trajectories(_FIXTURE_PATH)
    for key, traj in trajectories.items():
        summary = traj.summary()
        for axis in (
            "closure",
            "memory",
            "constraint",
            "persistence",
            "coherence",
        ):
            assert axis in summary, f"axis {axis} missing from group {key}"
            entry = summary[axis]
            for metric_name in (
                "n_total",
                "n_defined",
                "mean",
                "std",
                "drift",
                "volatility",
                "path_length",
            ):
                assert metric_name in entry, (
                    f"metric {metric_name} missing for axis {axis} in group {key}"
                )


# ----------------------------------------------------------------------
# PO-4 — Saturation in real data
# ----------------------------------------------------------------------


def _periodic_cycle_summary() -> dict[str, dict[str, float | int | None]]:
    trajectories = _load_grouped_trajectories(_FIXTURE_PATH)
    return trajectories[("PeriodicCycle", "period=2")].summary()


def test_po4_periodic_cycle_closure_is_saturated_at_one() -> None:
    closure = _periodic_cycle_summary()["closure"]
    assert closure["n_defined"] == 5
    assert closure["mean"] == pytest.approx(1.0)
    assert closure["drift"] == pytest.approx(0.0, abs=_SATURATION_TOL)
    assert closure["volatility"] == pytest.approx(0.0, abs=_SATURATION_TOL)
    assert closure["path_length"] == pytest.approx(0.0, abs=_SATURATION_TOL)


def test_po4_periodic_cycle_constraint_is_saturated_at_zero() -> None:
    constraint = _periodic_cycle_summary()["constraint"]
    assert constraint["n_defined"] == 5
    assert constraint["mean"] == pytest.approx(0.0)
    assert constraint["drift"] == pytest.approx(0.0, abs=_SATURATION_TOL)
    assert constraint["volatility"] == pytest.approx(0.0, abs=_SATURATION_TOL)
    assert constraint["path_length"] == pytest.approx(0.0, abs=_SATURATION_TOL)


def test_po4_periodic_cycle_persistence_is_saturated_at_zero() -> None:
    persistence = _periodic_cycle_summary()["persistence"]
    assert persistence["n_defined"] == 5
    assert persistence["mean"] == pytest.approx(0.0)
    assert persistence["drift"] == pytest.approx(0.0, abs=_SATURATION_TOL)
    assert persistence["volatility"] == pytest.approx(0.0, abs=_SATURATION_TOL)
    assert persistence["path_length"] == pytest.approx(0.0, abs=_SATURATION_TOL)


def test_po4_periodic_cycle_coherence_is_fully_undefined() -> None:
    coherence = _periodic_cycle_summary()["coherence"]
    assert coherence["n_total"] == 5
    assert coherence["n_defined"] == 0
    for metric in ("mean", "std", "drift", "volatility", "path_length"):
        assert coherence[metric] is None


def test_po4_periodic_cycle_memory_is_not_saturated() -> None:
    memory = _periodic_cycle_summary()["memory"]
    assert memory["n_defined"] == 5
    volatility = memory["volatility"]
    path_length = memory["path_length"]
    assert volatility is not None and volatility > 0.0
    assert path_length is not None and path_length > 0.0


def test_po4_kauffman_network_handles_interior_hole() -> None:
    """KauffmanNetwork coupling=0.5 seed=1 has every axis ``None``. The
    trajectory must still process; affected axes report n_defined < 5
    without raising."""
    trajectories = _load_grouped_trajectories(_FIXTURE_PATH)
    summary = trajectories[("KauffmanNetwork", "coupling=0.5")].summary()
    for axis in ("closure", "memory", "constraint", "persistence"):
        entry = summary[axis]
        assert entry["n_total"] == 5
        assert entry["n_defined"] == 4, (
            f"axis {axis}: expected 4 defined snapshots after dropping seed=1, "
            f"got {entry['n_defined']}"
        )


def test_po4_eca_system_closure_and_constraint_are_saturated() -> None:
    """ECASystem rule=30 saturates two of the four numeric axes in the
    Autonometrics zoo — locks the cross-system shape of LD-1."""
    trajectories = _load_grouped_trajectories(_FIXTURE_PATH)
    summary = trajectories[("ECASystem", "rule=30")].summary()
    closure = summary["closure"]
    constraint = summary["constraint"]
    assert closure["volatility"] == pytest.approx(0.0, abs=_SATURATION_TOL)
    assert closure["path_length"] == pytest.approx(0.0, abs=_SATURATION_TOL)
    assert constraint["volatility"] == pytest.approx(0.0, abs=_SATURATION_TOL)
    assert constraint["path_length"] == pytest.approx(0.0, abs=_SATURATION_TOL)
    # Memory varies across seeds, so volatility must be strictly positive
    memory = summary["memory"]
    assert memory["volatility"] is not None
    assert memory["volatility"] > 0.0
    # Sanity: standard deviation of values is positive too (and finite)
    assert memory["std"] is not None
    assert math.isfinite(memory["std"]) and memory["std"] > 0.0

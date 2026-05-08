"""Behavioural tests for the v0.2.0a0 generic adapters."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest
from autonometrics import AutonomyProfile

from autodynamics import ProfileTrajectory
from autodynamics.adapters import (
    BatchTrajectoryAdapter,
    CSVTrajectoryAdapter,
)

_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "autonometrics_v0_8_sample.csv"
)


# ----------------------------------------------------------------------
# CSVTrajectoryAdapter
# ----------------------------------------------------------------------


def test_csv_adapter_loads_fixture_into_a_single_trajectory() -> None:
    adapter = CSVTrajectoryAdapter()
    traj = adapter.load_path(_FIXTURE_PATH)
    assert len(traj) == 15
    assert traj.axes == (
        "closure",
        "memory",
        "constraint",
        "persistence",
        "coherence",
    )


def test_csv_adapter_treats_empty_cells_as_none() -> None:
    """The fixture has empty ``coherence`` cells everywhere — confirm
    they are surfaced as ``None`` snapshots, not coerced to 0.0."""
    adapter = CSVTrajectoryAdapter()
    traj = adapter.load_path(_FIXTURE_PATH)
    assert all(v is None for v in traj.axis_series("coherence"))


def test_csv_adapter_treats_whitespace_cells_as_none() -> None:
    rows = [
        {"closure": "0.5", "memory": "  ", "constraint": "", "persistence": "0.2", "coherence": ""},
    ]
    adapter = CSVTrajectoryAdapter()
    traj = adapter.load_rows(rows)
    snap = traj[0]
    assert snap.profile.closure == pytest.approx(0.5)
    assert snap.profile.memory is None
    assert snap.profile.constraint is None
    assert snap.profile.persistence == pytest.approx(0.2)
    assert snap.profile.coherence is None


def test_csv_adapter_missing_axis_column_yields_undefined_axis() -> None:
    """A CSV that does not declare a canonical axis column at all must
    treat that axis as fully undefined for every snapshot."""
    rows = [
        {"closure": "0.1", "memory": "0.2"},
        {"closure": "0.3", "memory": "0.4"},
    ]
    adapter = CSVTrajectoryAdapter()
    traj = adapter.load_rows(rows)
    assert traj.axis_series("closure") == [
        pytest.approx(0.1),
        pytest.approx(0.3),
    ]
    assert traj.axis_series("constraint") == [None, None]
    assert traj.axis_series("persistence") == [None, None]
    assert traj.axis_series("coherence") == [None, None]


def test_csv_adapter_extra_columns_are_ignored() -> None:
    rows = [
        {
            "class": "ECASystem",
            "params": "rule=30",
            "seed": "0",
            "closure": "1.0",
            "memory": "0.16",
            "constraint": "1.0",
            "persistence": "0.03",
            "coherence": "",
            "quadrant": "clockwork",
            "notes": "irrelevant",
        }
    ]
    adapter = CSVTrajectoryAdapter()
    traj = adapter.load_rows(rows)
    assert len(traj) == 1
    assert traj[0].profile.closure == pytest.approx(1.0)
    assert traj[0].profile.memory == pytest.approx(0.16)


def test_csv_adapter_preserves_row_order_when_no_order_column() -> None:
    rows = [
        {"closure": "0.3"},
        {"closure": "0.1"},
        {"closure": "0.5"},
        {"closure": "0.2"},
    ]
    adapter = CSVTrajectoryAdapter()
    traj = adapter.load_rows(rows)
    assert traj.axis_series("closure") == pytest.approx([0.3, 0.1, 0.5, 0.2])


def test_csv_adapter_sorts_by_order_column() -> None:
    rows = [
        {"step": "3", "closure": "0.3"},
        {"step": "1", "closure": "0.1"},
        {"step": "5", "closure": "0.5"},
        {"step": "2", "closure": "0.2"},
    ]
    adapter = CSVTrajectoryAdapter(order_column="step")
    traj = adapter.load_rows(rows)
    assert traj.axis_series("closure") == pytest.approx([0.1, 0.2, 0.3, 0.5])


def test_csv_adapter_sorts_by_order_column_numerically_not_lexically() -> None:
    """``"10"`` must sort after ``"2"`` — ints, not strings."""
    rows = [
        {"step": "10", "closure": "0.10"},
        {"step": "2", "closure": "0.02"},
        {"step": "1", "closure": "0.01"},
    ]
    adapter = CSVTrajectoryAdapter(order_column="step")
    traj = adapter.load_rows(rows)
    assert traj.axis_series("closure") == pytest.approx([0.01, 0.02, 0.10])


def test_csv_adapter_order_column_missing_in_row_raises() -> None:
    adapter = CSVTrajectoryAdapter(order_column="missing")
    with pytest.raises(KeyError):
        adapter.load_rows([{"closure": "0.1"}])


def test_csv_adapter_empty_order_column_value_raises() -> None:
    adapter = CSVTrajectoryAdapter(order_column="step")
    with pytest.raises(ValueError):
        adapter.load_rows(
            [
                {"step": "1", "closure": "0.1"},
                {"step": "", "closure": "0.2"},
            ]
        )


def test_csv_adapter_axes_argument_bounds_trajectory_axes() -> None:
    rows = [
        {"closure": "0.1", "memory": "0.4", "constraint": "0.2"},
        {"closure": "0.3", "memory": "0.5", "constraint": "0.6"},
    ]
    adapter = CSVTrajectoryAdapter(axes=("closure", "memory"))
    traj = adapter.load_rows(rows)
    assert traj.axes == ("closure", "memory")
    # Even though ``constraint`` was read into the profiles, the
    # trajectory only reports on the configured axes.
    assert "constraint" not in traj.to_dict()


def test_csv_adapter_round_trip_via_to_dict_preserves_axes() -> None:
    """Round-trip: build a trajectory, serialise it to CSV using
    ``to_dict`` + writer, reload with ``CSVTrajectoryAdapter``, verify
    the axis series match exactly."""
    source = ProfileTrajectory()
    profiles = [
        AutonomyProfile(
            ratio_endo_total=0.1,
            memory_endo_ratio=0.4,
            constraint_closure=None,
            rai_proxy_persistence=0.2,
            cba_theil_u=0.3,
        ),
        AutonomyProfile(
            ratio_endo_total=0.5,
            memory_endo_ratio=None,
            constraint_closure=0.7,
            rai_proxy_persistence=0.4,
            cba_theil_u=None,
        ),
        AutonomyProfile(
            ratio_endo_total=1.0,
            memory_endo_ratio=0.9,
            constraint_closure=0.6,
            rai_proxy_persistence=0.0,
            cba_theil_u=0.5,
        ),
    ]
    for p in profiles:
        source.append(p)

    serialised = source.to_dict()
    fields = list(serialised.keys())
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    for i in range(len(source)):
        writer.writerow(
            {
                axis: ("" if serialised[axis][i] is None else str(serialised[axis][i]))
                for axis in fields
            }
        )

    buffer.seek(0)
    rows = list(csv.DictReader(buffer))
    adapter = CSVTrajectoryAdapter()
    reloaded = adapter.load_rows(rows)

    assert len(reloaded) == len(source)
    for axis in (
        "closure",
        "memory",
        "constraint",
        "persistence",
        "coherence",
    ):
        original = source.axis_series(axis)
        recovered = reloaded.axis_series(axis)
        assert len(original) == len(recovered)
        for o, r in zip(original, recovered, strict=True):
            if o is None:
                assert r is None
            else:
                assert r == pytest.approx(o)


# ----------------------------------------------------------------------
# BatchTrajectoryAdapter
# ----------------------------------------------------------------------


def _profile(closure: float | None = None, memory: float | None = None) -> AutonomyProfile:
    return AutonomyProfile(
        ratio_endo_total=closure,
        memory_endo_ratio=memory,
    )


def test_batch_adapter_starts_empty() -> None:
    batch = BatchTrajectoryAdapter()
    assert len(batch) == 0
    assert batch.group_keys == ()
    assert batch.trajectories() == {}


def test_batch_adapter_groups_profiles_by_key() -> None:
    batch = BatchTrajectoryAdapter()
    batch.add("group_a", _profile(closure=0.1))
    batch.add("group_b", _profile(closure=0.5))
    batch.add("group_a", _profile(closure=0.2))
    batch.add("group_b", _profile(closure=0.6))
    assert len(batch) == 2
    assert batch.group_keys == ("group_a", "group_b")
    trajectories = batch.trajectories()
    assert sorted(trajectories.keys()) == ["group_a", "group_b"]
    assert trajectories["group_a"].axis_series("closure") == pytest.approx(
        [0.1, 0.2]
    )
    assert trajectories["group_b"].axis_series("closure") == pytest.approx(
        [0.5, 0.6]
    )


def test_batch_adapter_parallel_seeds_yield_equal_length_trajectories() -> None:
    """Brief contract: 'BatchTrajectoryAdapter con multiples seeds produce
    trayectorias paralelas con la misma longitud.'"""
    batch = BatchTrajectoryAdapter()
    seeds = list(range(5))
    for seed in seeds:
        batch.add(("ECASystem", "rule=30"), _profile(closure=1.0))
        batch.add(("ECASystem", "rule=110"), _profile(closure=0.7))
        batch.add(("PeriodicCycle", "period=2"), _profile(closure=1.0))
    trajectories = batch.trajectories()
    assert len(trajectories) == 3
    lengths = {len(t) for t in trajectories.values()}
    assert lengths == {len(seeds)}


def test_batch_adapter_preserves_first_insertion_order_of_keys() -> None:
    batch = BatchTrajectoryAdapter()
    batch.add("c", _profile(closure=0.1))
    batch.add("a", _profile(closure=0.2))
    batch.add("b", _profile(closure=0.3))
    batch.add("a", _profile(closure=0.4))
    assert batch.group_keys == ("c", "a", "b")


def test_batch_adapter_axes_argument_propagates_to_trajectories() -> None:
    batch = BatchTrajectoryAdapter(axes=("closure", "memory"))
    batch.add("g", _profile(closure=0.1, memory=0.4))
    traj = batch.trajectories()["g"]
    assert traj.axes == ("closure", "memory")


def test_batch_adapter_trajectories_does_not_mutate_state() -> None:
    batch = BatchTrajectoryAdapter()
    batch.add("g", _profile(closure=0.1))
    batch.add("g", _profile(closure=0.2))
    first = batch.trajectories()
    second = batch.trajectories()
    assert first is not second
    assert len(first["g"]) == 2
    assert len(second["g"]) == 2
    # Adding after a snapshot does not retroactively grow the previous result
    batch.add("g", _profile(closure=0.3))
    assert len(first["g"]) == 2


def test_batch_adapter_mean_summary_empty_batch_yields_all_none() -> None:
    batch = BatchTrajectoryAdapter()
    means = batch.mean_summary()
    for axis in (
        "closure",
        "memory",
        "constraint",
        "persistence",
        "coherence",
    ):
        for metric in ("mean", "std", "drift", "volatility", "path_length"):
            assert means[axis][metric] is None


def test_batch_adapter_mean_summary_averages_across_groups() -> None:
    """Two saturated groups (closure=1.0 and closure=0.0): the mean
    over groups of ``mean`` is 0.5; ``drift``, ``volatility``,
    ``path_length`` and ``std`` are all 0 in each group, so their batch
    means are 0."""
    batch = BatchTrajectoryAdapter()
    for _ in range(4):
        batch.add("high", _profile(closure=1.0))
        batch.add("low", _profile(closure=0.0))
    means = batch.mean_summary()
    closure = means["closure"]
    assert closure["mean"] == pytest.approx(0.5)
    assert closure["std"] == pytest.approx(0.0)
    assert closure["drift"] == pytest.approx(0.0)
    assert closure["volatility"] == pytest.approx(0.0)
    assert closure["path_length"] == pytest.approx(0.0)


def test_batch_adapter_mean_summary_excludes_none_groups() -> None:
    """One group has memory fully defined, another has memory fully
    None. The batch mean must use only the defined group, not penalise
    the average by including None as 0."""
    batch = BatchTrajectoryAdapter()
    for _ in range(4):
        batch.add("with_memory", _profile(closure=0.5, memory=0.4))
        batch.add("no_memory", _profile(closure=0.5, memory=None))
    means = batch.mean_summary()
    assert means["memory"]["mean"] == pytest.approx(0.4)


def test_batch_adapter_integration_with_csv_adapter_over_fixture() -> None:
    """End-to-end smoke: the same fixture used in test_diagnostics, here
    consumed via the public adapter pipeline (CSV adapter to load each
    row, batch adapter to group by ``(class, params)``)."""
    rows = list(csv.DictReader(_FIXTURE_PATH.open(encoding="utf-8")))
    csv_adapter = CSVTrajectoryAdapter()

    batch = BatchTrajectoryAdapter()
    for row in rows:
        single = csv_adapter.load_rows([row])
        assert len(single) == 1
        batch.add((row["class"], row["params"]), single[0].profile)

    trajectories = batch.trajectories()
    assert len(trajectories) == 3
    for traj in trajectories.values():
        assert len(traj) == 5

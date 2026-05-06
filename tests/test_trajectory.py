"""Behavioural tests for ProfileTrajectory and its companions."""

import pytest
from autonometrics import AutonomyProfile

from autodynamics import ProfileDelta, ProfileSnapshot, ProfileTrajectory


def _make_profile(
    closure: float | None = None,
    memory: float | None = None,
    coherence: float | None = None,
) -> AutonomyProfile:
    return AutonomyProfile(
        ratio_endo_total=closure,
        memory_endo_ratio=memory,
        cba_theil_u=coherence,
    )


def test_empty_trajectory_has_zero_length() -> None:
    traj = ProfileTrajectory()
    assert len(traj) == 0
    assert list(traj) == []


def test_append_returns_snapshot() -> None:
    traj = ProfileTrajectory()
    profile = _make_profile(closure=0.5, memory=0.4)
    snapshot = traj.append(profile)
    assert isinstance(snapshot, ProfileSnapshot)
    assert snapshot.index == 0
    assert snapshot.profile is profile


def test_append_increments_index() -> None:
    traj = ProfileTrajectory()
    s0 = traj.append(_make_profile(closure=0.1))
    s1 = traj.append(_make_profile(closure=0.2))
    s2 = traj.append(_make_profile(closure=0.3))
    assert (s0.index, s1.index, s2.index) == (0, 1, 2)
    assert len(traj) == 3


def test_getitem_returns_snapshot() -> None:
    traj = ProfileTrajectory()
    traj.append(_make_profile(closure=0.5))
    snap = traj[0]
    assert snap.index == 0
    assert snap.profile.closure == 0.5


def test_iteration_yields_snapshots_in_order() -> None:
    traj = ProfileTrajectory()
    for v in (0.1, 0.2, 0.3):
        traj.append(_make_profile(closure=v))
    indices = [s.index for s in traj]
    closures = [s.profile.closure for s in traj]
    assert indices == [0, 1, 2]
    assert closures == [0.1, 0.2, 0.3]


def test_axis_series_returns_values_and_nones() -> None:
    traj = ProfileTrajectory()
    traj.append(_make_profile(closure=0.5, memory=None))
    traj.append(_make_profile(closure=0.6, memory=0.4))
    assert traj.axis_series("closure") == [0.5, 0.6]
    assert traj.axis_series("memory") == [None, 0.4]


def test_axis_series_rejects_unknown_axis() -> None:
    traj = ProfileTrajectory()
    with pytest.raises(ValueError):
        traj.axis_series("nonsense")


def test_deltas_returns_consecutive_pairs() -> None:
    traj = ProfileTrajectory(axes=("closure",))
    traj.append(_make_profile(closure=0.1))
    traj.append(_make_profile(closure=0.4))
    traj.append(_make_profile(closure=0.6))
    deltas = traj.deltas()
    assert len(deltas) == 2
    assert deltas[0].from_index == 0 and deltas[0].to_index == 1
    assert deltas[0].deltas["closure"] == pytest.approx(0.3)
    assert deltas[1].from_index == 1 and deltas[1].to_index == 2
    assert deltas[1].deltas["closure"] == pytest.approx(0.2)


def test_deltas_yield_none_when_endpoint_is_none() -> None:
    traj = ProfileTrajectory(axes=("closure", "memory"))
    traj.append(_make_profile(closure=0.5, memory=None))
    traj.append(_make_profile(closure=0.6, memory=0.4))
    deltas = traj.deltas()
    assert deltas[0].deltas["closure"] == pytest.approx(0.1)
    assert deltas[0].deltas["memory"] is None


def test_delta_magnitude_uses_only_defined_axes() -> None:
    delta = ProfileDelta(
        from_index=0,
        to_index=1,
        deltas={"closure": 0.3, "memory": 0.4, "coherence": None},
    )
    assert delta.magnitude == pytest.approx(0.5)


def test_delta_magnitude_returns_none_when_all_axes_none() -> None:
    delta = ProfileDelta(
        from_index=0,
        to_index=1,
        deltas={"closure": None, "memory": None},
    )
    assert delta.magnitude is None


def test_empty_trajectory_path_length_is_none() -> None:
    traj = ProfileTrajectory()
    assert traj.total_path_length() is None


def test_single_snapshot_path_length_is_none() -> None:
    traj = ProfileTrajectory()
    traj.append(_make_profile(closure=0.5))
    assert traj.total_path_length() is None


def test_total_path_length_sums_magnitudes() -> None:
    traj = ProfileTrajectory(axes=("closure",))
    traj.append(_make_profile(closure=0.0))
    traj.append(_make_profile(closure=0.3))
    traj.append(_make_profile(closure=0.7))
    # |0.3 - 0.0| + |0.7 - 0.3| = 0.3 + 0.4 = 0.7
    assert traj.total_path_length() == pytest.approx(0.7)


def test_to_dict_returns_axis_series_per_axis() -> None:
    traj = ProfileTrajectory(axes=("closure", "memory"))
    traj.append(_make_profile(closure=0.5, memory=0.4))
    traj.append(_make_profile(closure=0.6, memory=None))
    result = traj.to_dict()
    assert set(result.keys()) == {"closure", "memory"}
    assert result["closure"] == [0.5, 0.6]
    assert result["memory"] == [0.4, None]


def test_init_rejects_unknown_axis() -> None:
    with pytest.raises(ValueError):
        ProfileTrajectory(axes=("closure", "nonsense"))


def test_init_rejects_duplicate_axes() -> None:
    with pytest.raises(ValueError):
        ProfileTrajectory(axes=("closure", "closure"))


def test_init_rejects_empty_axes_when_provided() -> None:
    with pytest.raises(ValueError):
        ProfileTrajectory(axes=[])


def test_default_axes_cover_all_five_canonical() -> None:
    traj = ProfileTrajectory()
    assert traj.axes == ("closure", "memory", "constraint", "persistence", "coherence")

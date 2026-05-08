"""Behavioural tests for the v0.2.0a0 algebra primitives on ``ProfileTrajectory``."""

from __future__ import annotations

import math

import pytest
from autonometrics import AutonomyProfile

from autodynamics import ProfileTrajectory


def _make_profile(
    closure: float | None = None,
    memory: float | None = None,
    constraint: float | None = None,
    persistence: float | None = None,
    coherence: float | None = None,
) -> AutonomyProfile:
    return AutonomyProfile(
        ratio_endo_total=closure,
        memory_endo_ratio=memory,
        constraint_closure=constraint,
        rai_proxy_persistence=persistence,
        cba_theil_u=coherence,
    )


def _build(values: list[float | None], axis: str = "closure") -> ProfileTrajectory:
    """Helper: build a single-axis trajectory from a list of values."""
    traj = ProfileTrajectory(axes=(axis,))
    for v in values:
        traj.append(_make_profile(**{axis: v}))
    return traj


# ----------------------------------------------------------------------
# velocities
# ----------------------------------------------------------------------


def test_velocities_empty_trajectory_returns_empty_list_per_axis() -> None:
    traj = ProfileTrajectory(axes=("closure", "memory"))
    assert traj.velocities("closure") == []
    assert traj.velocities() == {"closure": [], "memory": []}


def test_velocities_single_snapshot_returns_empty_list() -> None:
    traj = _build([0.5])
    assert traj.velocities("closure") == []


def test_velocities_monotone_increasing_are_all_positive() -> None:
    traj = _build([0.0, 0.2, 0.5, 0.9])
    velocities = traj.velocities("closure")
    assert velocities == pytest.approx([0.2, 0.3, 0.4])
    assert all(v > 0 for v in velocities)


def test_velocities_constant_trajectory_are_all_zero() -> None:
    traj = _build([0.4, 0.4, 0.4, 0.4])
    assert traj.velocities("closure") == pytest.approx([0.0, 0.0, 0.0])


def test_velocities_oscillating_trajectory_alternate_sign() -> None:
    traj = _build([0.2, 0.6, 0.2, 0.6])
    velocities = traj.velocities("closure")
    assert velocities == pytest.approx([0.4, -0.4, 0.4])


def test_velocities_mosaic_dropout_emits_none_at_endpoints() -> None:
    traj = ProfileTrajectory(axes=("closure",))
    traj.append(_make_profile(closure=None))
    traj.append(_make_profile(closure=0.3))
    traj.append(_make_profile(closure=0.5))
    traj.append(_make_profile(closure=None))
    assert traj.velocities("closure") == [None, pytest.approx(0.2), None]


def test_velocities_default_returns_dict_over_configured_axes() -> None:
    traj = ProfileTrajectory(axes=("closure", "memory"))
    traj.append(_make_profile(closure=0.1, memory=0.4))
    traj.append(_make_profile(closure=0.3, memory=0.5))
    out = traj.velocities()
    assert set(out.keys()) == {"closure", "memory"}
    assert out["closure"] == pytest.approx([0.2])
    assert out["memory"] == pytest.approx([0.1])


def test_velocities_rejects_unknown_axis() -> None:
    traj = _build([0.1, 0.2])
    with pytest.raises(ValueError):
        traj.velocities("nonsense")


def test_velocities_rejects_axis_outside_configured_but_canonical() -> None:
    """Canonical axis name still resolves through axis_series; behaviour is
    documented to operate over the recorded profiles regardless of what was
    configured. This locks the current contract: any canonical name works."""
    traj = ProfileTrajectory(axes=("closure",))
    traj.append(_make_profile(closure=0.1, memory=0.4))
    traj.append(_make_profile(closure=0.2, memory=0.6))
    assert traj.velocities("memory") == pytest.approx([0.2])


# ----------------------------------------------------------------------
# accelerations
# ----------------------------------------------------------------------


def test_accelerations_short_trajectory_is_empty() -> None:
    assert _build([]).accelerations("closure") == []
    assert _build([0.5]).accelerations("closure") == []
    assert _build([0.5, 0.6]).accelerations("closure") == []


def test_accelerations_constant_velocity_is_zero() -> None:
    traj = _build([0.0, 0.2, 0.4, 0.6])
    assert traj.accelerations("closure") == pytest.approx([0.0, 0.0])


def test_accelerations_quadratic_growth_is_positive() -> None:
    traj = _build([0.0, 0.1, 0.3, 0.6, 1.0])
    accel = traj.accelerations("closure")
    assert all(a > 0 for a in accel if a is not None)


def test_accelerations_mosaic_dropout_in_velocity_propagates() -> None:
    """A trajectory with a hole produces ``None`` velocities around the hole,
    which then propagate to several ``None`` accelerations. Defined regions
    of the trajectory still yield numeric accelerations."""
    traj = ProfileTrajectory(axes=("closure",))
    # series:        [0.0, 0.2, 0.5, 1.0, None, 1.5, 2.5]
    # velocities:    [0.2, 0.3, 0.5, None, None, 1.0]
    # accelerations: [0.1, 0.2, None, None, None]
    for v in [0.0, 0.2, 0.5, 1.0, None, 1.5, 2.5]:
        traj.append(_make_profile(closure=v))
    accel = traj.accelerations("closure")
    assert accel == [
        pytest.approx(0.1),
        pytest.approx(0.2),
        None,
        None,
        None,
    ]


# ----------------------------------------------------------------------
# drift
# ----------------------------------------------------------------------


def test_drift_constant_trajectory_is_zero() -> None:
    traj = _build([0.4, 0.4, 0.4])
    assert traj.drift("closure") == pytest.approx(0.0)


def test_drift_monotone_trajectory_equals_total_change() -> None:
    traj = _build([0.1, 0.3, 0.7])
    assert traj.drift("closure") == pytest.approx(0.6)


def test_drift_skips_internal_nones() -> None:
    traj = _build([None, 0.3, 0.5, None, 0.7])
    assert traj.drift("closure") == pytest.approx(0.4)


def test_drift_with_fewer_than_two_defined_returns_none() -> None:
    assert _build([]).drift("closure") is None
    assert _build([0.5]).drift("closure") is None
    assert _build([None, 0.5, None]).drift("closure") is None
    assert _build([None, None, None]).drift("closure") is None


def test_drift_default_returns_dict() -> None:
    traj = ProfileTrajectory(axes=("closure", "memory"))
    traj.append(_make_profile(closure=0.1, memory=0.5))
    traj.append(_make_profile(closure=0.4, memory=0.5))
    out = traj.drift()
    assert out == {"closure": pytest.approx(0.3), "memory": pytest.approx(0.0)}


# ----------------------------------------------------------------------
# volatility
# ----------------------------------------------------------------------


def test_volatility_constant_trajectory_is_zero() -> None:
    traj = _build([0.4, 0.4, 0.4, 0.4])
    assert traj.volatility("closure") == pytest.approx(0.0)


def test_volatility_with_fewer_than_two_velocities_is_none() -> None:
    assert _build([]).volatility("closure") is None
    assert _build([0.5]).volatility("closure") is None
    assert _build([0.5, 0.6]).volatility("closure") is None


def test_volatility_known_values_match_sample_std() -> None:
    traj = _build([0.0, 0.2, 0.4, 1.0])
    velocities = [0.2, 0.2, 0.6]
    mu = sum(velocities) / 3
    expected = math.sqrt(sum((v - mu) ** 2 for v in velocities) / 2)
    assert traj.volatility("closure") == pytest.approx(expected)


def test_volatility_oscillating_trajectory_is_positive() -> None:
    traj = _build([0.2, 0.6, 0.2, 0.6, 0.2])
    drift = traj.drift("closure")
    volat = traj.volatility("closure")
    path = traj.path_length_per_axis()["closure"]
    assert drift == pytest.approx(0.0)
    assert volat is not None and volat > 0
    assert path is not None and path > abs(drift or 0)


# ----------------------------------------------------------------------
# path_length_per_axis
# ----------------------------------------------------------------------


def test_path_length_per_axis_constant_is_zero() -> None:
    traj = _build([0.4, 0.4, 0.4])
    assert traj.path_length_per_axis() == {"closure": pytest.approx(0.0)}


def test_path_length_per_axis_monotone_equals_drift_in_magnitude() -> None:
    traj = _build([0.1, 0.3, 0.7])
    assert traj.path_length_per_axis()["closure"] == pytest.approx(0.6)


def test_path_length_per_axis_oscillating_exceeds_drift() -> None:
    traj = _build([0.2, 0.6, 0.2])
    assert traj.path_length_per_axis()["closure"] == pytest.approx(0.8)


def test_path_length_per_axis_all_none_axis_returns_none() -> None:
    traj = _build([None, None, None])
    assert traj.path_length_per_axis()["closure"] is None


def test_path_length_per_axis_short_trajectory_returns_none() -> None:
    assert _build([]).path_length_per_axis()["closure"] is None
    assert _build([0.5]).path_length_per_axis()["closure"] is None


def test_path_length_per_axis_partial_dropout_skips_nones() -> None:
    traj = _build([0.1, None, 0.4, 0.5])
    # velocities = [None, None, 0.1] -> sum |v| = 0.1
    assert traj.path_length_per_axis()["closure"] == pytest.approx(0.1)


# ----------------------------------------------------------------------
# rolling_mean
# ----------------------------------------------------------------------


def test_rolling_mean_basic_window_three() -> None:
    traj = _build([0.0, 1.0, 2.0, 3.0, 4.0])
    result = traj.rolling_mean("closure", window=3)
    assert result[0] is None and result[1] is None
    assert result[2] == pytest.approx(1.0)
    assert result[3] == pytest.approx(2.0)
    assert result[4] == pytest.approx(3.0)


def test_rolling_mean_window_larger_than_length_all_none() -> None:
    traj = _build([0.1, 0.2, 0.3])
    assert traj.rolling_mean("closure", window=10) == [None, None, None]


def test_rolling_mean_window_one_returns_series() -> None:
    """``window=1`` is a degenerate but supported case: ceil(1/2)=1, so
    every defined slot emits its own value and ``None`` slots stay ``None``."""
    traj = _build([0.1, None, 0.3])
    assert traj.rolling_mean("closure", window=1) == [
        pytest.approx(0.1),
        None,
        pytest.approx(0.3),
    ]


def test_rolling_mean_with_holes_emits_none_when_below_threshold() -> None:
    traj = _build([0.0, None, None, 1.0, 2.0])
    result = traj.rolling_mean("closure", window=3)
    # i=0,1 -> None (window not yet fitting)
    # i=2: window=[0.0, None, None] -> 1 defined < ceil(3/2)=2 -> None
    # i=3: window=[None, None, 1.0] -> 1 defined < 2 -> None
    # i=4: window=[None, 1.0, 2.0] -> 2 defined >= 2 -> mean(1.0, 2.0) = 1.5
    assert result == [None, None, None, None, pytest.approx(1.5)]


def test_rolling_mean_rejects_unknown_axis() -> None:
    traj = _build([0.1, 0.2, 0.3])
    with pytest.raises(ValueError):
        traj.rolling_mean("nonsense", window=2)


def test_rolling_mean_rejects_non_positive_window() -> None:
    traj = _build([0.1, 0.2, 0.3])
    with pytest.raises(ValueError):
        traj.rolling_mean("closure", window=0)
    with pytest.raises(ValueError):
        traj.rolling_mean("closure", window=-1)


def test_rolling_mean_rejects_bool_window() -> None:
    traj = _build([0.1, 0.2, 0.3])
    with pytest.raises(TypeError):
        traj.rolling_mean("closure", window=True)


def test_rolling_mean_rejects_non_int_window() -> None:
    traj = _build([0.1, 0.2, 0.3])
    with pytest.raises(TypeError):
        traj.rolling_mean("closure", window=2.5)  # type: ignore[arg-type]


# ----------------------------------------------------------------------
# rolling_std
# ----------------------------------------------------------------------


def test_rolling_std_window_three_constant_is_zero_after_warmup() -> None:
    traj = _build([0.5, 0.5, 0.5, 0.5])
    result = traj.rolling_std("closure", window=3)
    assert result[0] is None and result[1] is None
    assert result[2] == pytest.approx(0.0)
    assert result[3] == pytest.approx(0.0)


def test_rolling_std_window_one_is_always_none() -> None:
    """Sample std of a single observation is undefined regardless of value."""
    traj = _build([0.1, 0.2, 0.3])
    assert traj.rolling_std("closure", window=1) == [None, None, None]


def test_rolling_std_window_larger_than_length_all_none() -> None:
    traj = _build([0.1, 0.2])
    assert traj.rolling_std("closure", window=5) == [None, None]


def test_rolling_std_known_window_three_values() -> None:
    traj = _build([0.0, 1.0, 2.0])
    # i=2: window=[0.0, 1.0, 2.0], mu=1.0, var = (1+0+1)/2 = 1.0, std=1.0
    result = traj.rolling_std("closure", window=3)
    assert result == [None, None, pytest.approx(1.0)]


def test_rolling_std_below_two_defined_emits_none() -> None:
    traj = _build([0.0, None, None, 1.0])
    result = traj.rolling_std("closure", window=3)
    # No window of 3 contains >= 2 defined values where the trailing index
    # also satisfies i >= window-1 with window-mid threshold. Verify all None.
    assert result == [None, None, None, None]


# ----------------------------------------------------------------------
# summary
# ----------------------------------------------------------------------


def test_summary_keys_match_specification() -> None:
    traj = ProfileTrajectory(axes=("closure",))
    traj.append(_make_profile(closure=0.1))
    traj.append(_make_profile(closure=0.3))
    traj.append(_make_profile(closure=0.7))
    summary = traj.summary()
    assert set(summary.keys()) == {"closure"}
    expected_metrics = {
        "n_total",
        "n_defined",
        "mean",
        "std",
        "drift",
        "volatility",
        "path_length",
    }
    assert set(summary["closure"].keys()) == expected_metrics


def test_summary_counts_are_consistent() -> None:
    traj = ProfileTrajectory(axes=("closure", "memory"))
    traj.append(_make_profile(closure=0.1, memory=None))
    traj.append(_make_profile(closure=0.3, memory=0.4))
    traj.append(_make_profile(closure=None, memory=0.5))
    summary = traj.summary()
    assert summary["closure"]["n_total"] == 3
    assert summary["closure"]["n_defined"] == 2
    assert summary["memory"]["n_total"] == 3
    assert summary["memory"]["n_defined"] == 2


def test_summary_fully_undefined_axis_yields_nones() -> None:
    traj = ProfileTrajectory(axes=("closure", "memory"))
    traj.append(_make_profile(closure=0.1, memory=None))
    traj.append(_make_profile(closure=0.3, memory=None))
    summary = traj.summary()
    assert summary["memory"]["n_total"] == 2
    assert summary["memory"]["n_defined"] == 0
    for metric in ("mean", "std", "drift", "volatility", "path_length"):
        assert summary["memory"][metric] is None


def test_summary_constant_trajectory_drift_volatility_zero() -> None:
    traj = _build([0.4, 0.4, 0.4, 0.4])
    summary = traj.summary()
    assert summary["closure"]["mean"] == pytest.approx(0.4)
    assert summary["closure"]["std"] == pytest.approx(0.0)
    assert summary["closure"]["drift"] == pytest.approx(0.0)
    assert summary["closure"]["volatility"] == pytest.approx(0.0)
    assert summary["closure"]["path_length"] == pytest.approx(0.0)


def test_summary_empty_trajectory_yields_zero_counts_and_nones() -> None:
    traj = ProfileTrajectory(axes=("closure",))
    summary = traj.summary()
    assert summary["closure"]["n_total"] == 0
    assert summary["closure"]["n_defined"] == 0
    for metric in ("mean", "std", "drift", "volatility", "path_length"):
        assert summary["closure"][metric] is None

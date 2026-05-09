"""Behavioural tests for ``autodynamics.envelope`` (v0.4.0a0).

The tests in this file lock in the locked decisions documented in
``docs/ENVELOPE_DIAGNOSTICS.md``. Smoke tests live in
``tests/test_envelope_smoke.py``.
"""

from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest
from autonometrics import AutonomyProfile

from autodynamics import (
    ContainmentResult,
    ContainmentVerdict,
    Envelope,
    ProfileTrajectory,
)


# ----------------------------------------------------------------------
# Fixtures / helpers
# ----------------------------------------------------------------------


def _profile(
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


def _trajectory(rows: list[dict[str, float | None]]) -> ProfileTrajectory:
    traj = ProfileTrajectory(
        axes=("closure", "memory", "constraint", "persistence", "coherence")
    )
    for row in rows:
        traj.append(_profile(**row))
    return traj


# ----------------------------------------------------------------------
# Construction and validation
# ----------------------------------------------------------------------


def test_default_envelope_has_no_bounded_axes() -> None:
    env = Envelope()
    assert env.bounds == {}
    assert env.axes == ()


def test_envelope_accepts_arbitrary_axis_names() -> None:
    env = Envelope(bounds={"foo": (0.0, 1.0), "bar": (-1.0, 1.0)})
    assert "foo" in env
    assert "bar" in env


def test_envelope_axes_property_is_lex_sorted() -> None:
    env = Envelope(
        bounds={"persistence": (0.0, 1.0), "closure": (0.0, 1.0)}
    )
    assert env.axes == ("closure", "persistence")


def test_envelope_normalises_int_bounds_to_float() -> None:
    env = Envelope(bounds={"closure": (0, 1)})
    lo, hi = env.bounds["closure"]
    assert isinstance(lo, float)
    assert isinstance(hi, float)


def test_envelope_rejects_non_mapping_bounds() -> None:
    with pytest.raises(TypeError):
        Envelope(bounds=[("closure", (0.0, 1.0))])  # type: ignore[arg-type]


def test_envelope_rejects_non_string_axis() -> None:
    with pytest.raises(TypeError):
        Envelope(bounds={1: (0.0, 1.0)})  # type: ignore[dict-item]


def test_envelope_rejects_non_tuple_interval() -> None:
    with pytest.raises(TypeError):
        Envelope(bounds={"closure": [0.0, 1.0]})  # type: ignore[dict-item]


def test_envelope_rejects_three_element_interval() -> None:
    with pytest.raises(TypeError):
        Envelope(bounds={"closure": (0.0, 0.5, 1.0)})  # type: ignore[dict-item]


def test_envelope_rejects_non_numeric_bounds() -> None:
    with pytest.raises(TypeError):
        Envelope(bounds={"closure": ("zero", "one")})  # type: ignore[dict-item]


def test_envelope_rejects_lo_strictly_greater_than_hi() -> None:
    with pytest.raises(ValueError):
        Envelope(bounds={"closure": (0.7, 0.3)})


def test_envelope_accepts_lo_equal_to_hi() -> None:
    env = Envelope(bounds={"closure": (0.5, 0.5)})
    assert env.bounds["closure"] == (0.5, 0.5)


def test_envelope_rejects_positive_infinity_bound() -> None:
    with pytest.raises(ValueError):
        Envelope(bounds={"closure": (0.0, math.inf)})


def test_envelope_rejects_nan_bound() -> None:
    with pytest.raises(ValueError):
        Envelope(bounds={"closure": (math.nan, 1.0)})


def test_envelope_is_frozen() -> None:
    env = Envelope(bounds={"closure": (0.0, 1.0)})
    with pytest.raises(FrozenInstanceError):
        env.bounds = {}  # type: ignore[misc]


# ----------------------------------------------------------------------
# evaluate — verdict semantics
# ----------------------------------------------------------------------


def test_evaluate_unbounded_envelope_is_inside_for_any_profile() -> None:
    env = Envelope()
    result = env.evaluate(_profile(closure=999.0))
    assert result.verdict == ContainmentVerdict.INSIDE
    assert result.per_axis == {}


def test_evaluate_at_lower_boundary_is_inside() -> None:
    env = Envelope(bounds={"closure": (0.4, 0.9)})
    result = env.evaluate(_profile(closure=0.4))
    assert result.verdict == ContainmentVerdict.INSIDE


def test_evaluate_at_upper_boundary_is_inside() -> None:
    env = Envelope(bounds={"closure": (0.4, 0.9)})
    result = env.evaluate(_profile(closure=0.9))
    assert result.verdict == ContainmentVerdict.INSIDE


def test_evaluate_just_below_lower_boundary_is_outside() -> None:
    env = Envelope(bounds={"closure": (0.4, 0.9)})
    result = env.evaluate(_profile(closure=0.4 - 1e-9))
    assert result.verdict == ContainmentVerdict.OUTSIDE
    assert result.violated_axes == ("closure",)


def test_evaluate_just_above_upper_boundary_is_outside() -> None:
    env = Envelope(bounds={"closure": (0.4, 0.9)})
    result = env.evaluate(_profile(closure=0.9 + 1e-9))
    assert result.verdict == ContainmentVerdict.OUTSIDE
    assert result.violated_axes == ("closure",)


def test_evaluate_per_axis_only_contains_bounded_axes() -> None:
    env = Envelope(bounds={"closure": (0.0, 1.0)})
    result = env.evaluate(_profile(closure=0.5, memory=99.0))
    assert set(result.per_axis.keys()) == {"closure"}


def test_evaluate_outside_dominates_undefined_in_aggregation() -> None:
    """LD-3: any OUTSIDE forces global OUTSIDE, even when other axes
    are UNDEFINED."""
    env = Envelope(bounds={"closure": (0.0, 0.5), "memory": (0.0, 1.0)})
    result = env.evaluate(_profile(closure=0.9, memory=None))
    assert result.verdict == ContainmentVerdict.OUTSIDE
    assert result.violated_axes == ("closure",)
    assert result.undefined_axes == ("memory",)


def test_evaluate_undefined_dominates_inside_in_aggregation() -> None:
    """LD-3: when no axis is OUTSIDE but some are UNDEFINED, the
    global verdict is UNDEFINED."""
    env = Envelope(bounds={"closure": (0.0, 1.0), "memory": (0.0, 1.0)})
    result = env.evaluate(_profile(closure=0.5, memory=None))
    assert result.verdict == ContainmentVerdict.UNDEFINED
    assert result.violated_axes == ()
    assert result.undefined_axes == ("memory",)


def test_evaluate_all_inside_yields_inside() -> None:
    env = Envelope(
        bounds={
            "closure": (0.0, 1.0),
            "memory": (0.0, 1.0),
            "constraint": (0.0, 1.0),
        }
    )
    result = env.evaluate(_profile(closure=0.5, memory=0.3, constraint=0.7))
    assert result.verdict == ContainmentVerdict.INSIDE


def test_evaluate_nan_value_is_undefined() -> None:
    env = Envelope(bounds={"closure": (0.0, 1.0)})
    result = env.evaluate({"closure": math.nan})
    assert result.verdict == ContainmentVerdict.UNDEFINED


def test_evaluate_positive_infinity_is_undefined() -> None:
    env = Envelope(bounds={"closure": (0.0, 1.0)})
    result = env.evaluate({"closure": math.inf})
    assert result.verdict == ContainmentVerdict.UNDEFINED


def test_evaluate_returns_containment_result_dataclass() -> None:
    env = Envelope(bounds={"closure": (0.0, 1.0)})
    result = env.evaluate(_profile(closure=0.5))
    assert isinstance(result, ContainmentResult)
    assert isinstance(result.violated_axes, tuple)
    assert isinstance(result.undefined_axes, tuple)
    assert isinstance(result.reasons, tuple)


def test_evaluate_reasons_are_human_readable() -> None:
    env = Envelope(bounds={"closure": (0.4, 0.9)})
    result = env.evaluate(_profile(closure=0.95))
    assert len(result.reasons) == 1
    reason = result.reasons[0]
    assert "closure" in reason
    assert "outside" in reason


# ----------------------------------------------------------------------
# evaluate — input types
# ----------------------------------------------------------------------


def test_evaluate_accepts_mapping_with_full_axes() -> None:
    env = Envelope(bounds={"closure": (0.0, 1.0)})
    result = env.evaluate({"closure": 0.5})
    assert result.verdict == ContainmentVerdict.INSIDE


def test_evaluate_mapping_missing_bounded_axis_is_undefined() -> None:
    env = Envelope(bounds={"closure": (0.0, 1.0), "memory": (0.0, 1.0)})
    result = env.evaluate({"closure": 0.5})
    assert result.verdict == ContainmentVerdict.UNDEFINED
    assert "memory" in result.undefined_axes


def test_evaluate_mapping_with_none_value_is_undefined() -> None:
    env = Envelope(bounds={"closure": (0.0, 1.0)})
    result = env.evaluate({"closure": None})
    assert result.verdict == ContainmentVerdict.UNDEFINED


def test_evaluate_rejects_invalid_type() -> None:
    env = Envelope(bounds={"closure": (0.0, 1.0)})
    with pytest.raises(TypeError):
        env.evaluate(42)  # type: ignore[arg-type]


# ----------------------------------------------------------------------
# contains shortcut
# ----------------------------------------------------------------------


def test_contains_returns_true_only_for_inside_verdict() -> None:
    env = Envelope(bounds={"closure": (0.0, 0.5)})
    assert env.contains(_profile(closure=0.3)) is True


def test_contains_returns_false_for_outside_verdict() -> None:
    env = Envelope(bounds={"closure": (0.0, 0.5)})
    assert env.contains(_profile(closure=0.9)) is False


def test_contains_returns_false_for_undefined_verdict() -> None:
    env = Envelope(bounds={"closure": (0.0, 0.5)})
    assert env.contains(_profile(closure=None)) is False


# ----------------------------------------------------------------------
# from_trajectory
# ----------------------------------------------------------------------


def test_from_trajectory_basic_mean_and_std() -> None:
    rows = [
        {"closure": 0.4},
        {"closure": 0.5},
        {"closure": 0.6},
    ]
    traj = _trajectory(rows)
    env = Envelope.from_trajectory(traj, width_multiplier=2.0)
    lo, hi = env.bounds["closure"]
    # mean = 0.5, std = 0.1; bounds = (0.5 - 0.2, 0.5 + 0.2)
    assert lo == pytest.approx(0.3, abs=1e-9)
    assert hi == pytest.approx(0.7, abs=1e-9)


def test_from_trajectory_drops_axes_with_fewer_than_two_defined_values() -> None:
    rows = [
        {"closure": 0.5, "memory": None},
        {"closure": 0.6, "memory": None},
    ]
    traj = _trajectory(rows)
    env = Envelope.from_trajectory(traj)
    assert "closure" in env
    assert "memory" not in env


def test_from_trajectory_empty_trajectory_yields_empty_envelope() -> None:
    traj = _trajectory([])
    env = Envelope.from_trajectory(traj)
    assert env.axes == ()


def test_from_trajectory_single_snapshot_yields_empty_envelope() -> None:
    rows = [{"closure": 0.5}]
    traj = _trajectory(rows)
    env = Envelope.from_trajectory(traj)
    assert env.axes == ()


def test_from_trajectory_axes_argument_restricts_output() -> None:
    rows = [
        {"closure": 0.4, "memory": 0.2, "constraint": 0.7},
        {"closure": 0.5, "memory": 0.3, "constraint": 0.8},
        {"closure": 0.6, "memory": 0.4, "constraint": 0.9},
    ]
    traj = _trajectory(rows)
    env = Envelope.from_trajectory(traj, axes=["closure"])
    assert env.axes == ("closure",)


def test_from_trajectory_axes_argument_unknown_axis_silently_ignored() -> None:
    rows = [
        {"closure": 0.4},
        {"closure": 0.5},
    ]
    traj = _trajectory(rows)
    env = Envelope.from_trajectory(
        traj, axes=["closure", "no_such_axis"]
    )
    assert env.axes == ("closure",)


def test_from_trajectory_width_multiplier_zero_yields_point_interval() -> None:
    rows = [
        {"closure": 0.4},
        {"closure": 0.5},
        {"closure": 0.6},
    ]
    traj = _trajectory(rows)
    env = Envelope.from_trajectory(traj, width_multiplier=0.0)
    lo, hi = env.bounds["closure"]
    assert lo == pytest.approx(0.5, abs=1e-9)
    assert hi == pytest.approx(0.5, abs=1e-9)


def test_from_trajectory_saturated_axis_yields_point_interval() -> None:
    """Constant axis has std = 0, so bounds collapse to (mean, mean)."""
    rows = [
        {"closure": 0.5},
        {"closure": 0.5},
        {"closure": 0.5},
    ]
    traj = _trajectory(rows)
    env = Envelope.from_trajectory(traj, width_multiplier=2.0)
    lo, hi = env.bounds["closure"]
    assert lo == pytest.approx(0.5, abs=1e-9)
    assert hi == pytest.approx(0.5, abs=1e-9)


def test_from_trajectory_rejects_negative_width_multiplier() -> None:
    rows = [{"closure": 0.5}, {"closure": 0.6}]
    traj = _trajectory(rows)
    with pytest.raises(ValueError):
        Envelope.from_trajectory(traj, width_multiplier=-0.5)


def test_from_trajectory_rejects_non_finite_width_multiplier() -> None:
    rows = [{"closure": 0.5}, {"closure": 0.6}]
    traj = _trajectory(rows)
    with pytest.raises(ValueError):
        Envelope.from_trajectory(traj, width_multiplier=math.inf)


def test_from_trajectory_rejects_non_trajectory_input() -> None:
    with pytest.raises(TypeError):
        Envelope.from_trajectory({"closure": [0.4, 0.5]})  # type: ignore[arg-type]


def test_from_trajectory_with_mosaic_dropout_uses_defined_subset() -> None:
    """Per LD-2, ``from_trajectory`` defers to ``summary()``, which
    runs over the defined sub-list."""
    rows = [
        {"closure": 0.4, "memory": None},
        {"closure": 0.5, "memory": 0.2},
        {"closure": 0.6, "memory": 0.3},
        {"closure": None, "memory": 0.4},
    ]
    traj = _trajectory(rows)
    env = Envelope.from_trajectory(traj, width_multiplier=1.0)
    assert "closure" in env
    assert "memory" in env


def test_from_trajectory_is_deterministic() -> None:
    rows = [
        {"closure": 0.4, "memory": 0.2},
        {"closure": 0.5, "memory": 0.3},
        {"closure": 0.6, "memory": 0.4},
    ]
    traj_1 = _trajectory(rows)
    traj_2 = _trajectory(rows)
    env_1 = Envelope.from_trajectory(traj_1, width_multiplier=2.0)
    env_2 = Envelope.from_trajectory(traj_2, width_multiplier=2.0)
    assert env_1.bounds == env_2.bounds


# ----------------------------------------------------------------------
# Round trip: from_trajectory -> evaluate
# ----------------------------------------------------------------------


def test_from_trajectory_round_trip_mean_profile_is_inside() -> None:
    rows = [
        {"closure": 0.4, "memory": 0.2},
        {"closure": 0.5, "memory": 0.3},
        {"closure": 0.6, "memory": 0.4},
    ]
    traj = _trajectory(rows)
    env = Envelope.from_trajectory(traj, width_multiplier=2.0)
    mean_profile = _profile(closure=0.5, memory=0.3)
    assert env.contains(mean_profile)


def test_from_trajectory_round_trip_far_profile_is_outside() -> None:
    rows = [
        {"closure": 0.4, "memory": 0.2},
        {"closure": 0.5, "memory": 0.3},
        {"closure": 0.6, "memory": 0.4},
    ]
    traj = _trajectory(rows)
    env = Envelope.from_trajectory(traj, width_multiplier=2.0)
    far_profile = _profile(closure=10.0, memory=0.3)
    result = env.evaluate(far_profile)
    assert result.verdict == ContainmentVerdict.OUTSIDE


# ----------------------------------------------------------------------
# ContainmentResult invariants
# ----------------------------------------------------------------------


def test_containment_result_rejects_non_enum_verdict() -> None:
    with pytest.raises(TypeError):
        ContainmentResult(
            verdict="INSIDE",  # type: ignore[arg-type]
            per_axis={},
            violated_axes=(),
            undefined_axes=(),
            reasons=(),
        )


def test_containment_verdict_str_equality_compatibility() -> None:
    """ContainmentVerdict inherits from str, so str comparisons work."""
    assert ContainmentVerdict.INSIDE == "INSIDE"
    assert ContainmentVerdict.OUTSIDE == "OUTSIDE"
    assert ContainmentVerdict.UNDEFINED == "UNDEFINED"

"""Smoke tests for ``autodynamics.envelope``."""

from __future__ import annotations

import pytest
from autonometrics import AutonomyProfile

from autodynamics import (
    ContainmentResult,
    ContainmentVerdict,
    Envelope,
    ProfileTrajectory,
)


def _profile(
    closure: float | None = None,
    memory: float | None = None,
) -> AutonomyProfile:
    return AutonomyProfile(
        ratio_endo_total=closure,
        memory_endo_ratio=memory,
        constraint_closure=None,
        rai_proxy_persistence=None,
        cba_theil_u=None,
    )


def test_envelope_imports_at_top_level() -> None:
    from autodynamics import Envelope, ContainmentResult, ContainmentVerdict
    assert Envelope is not None
    assert ContainmentResult is not None
    assert ContainmentVerdict is not None


def test_envelope_submodule_imports() -> None:
    from autodynamics.envelope import (
        Envelope,
        ContainmentResult,
        ContainmentVerdict,
    )
    assert Envelope is not None
    assert ContainmentResult is not None
    assert ContainmentVerdict is not None


def test_containment_verdict_members() -> None:
    assert ContainmentVerdict.INSIDE.value == "INSIDE"
    assert ContainmentVerdict.OUTSIDE.value == "OUTSIDE"
    assert ContainmentVerdict.UNDEFINED.value == "UNDEFINED"


def test_envelope_default_construction_is_unbounded() -> None:
    env = Envelope()
    assert env.axes == ()
    assert len(env) == 0


def test_envelope_explicit_bounds_round_trip() -> None:
    env = Envelope(bounds={"closure": (0.0, 1.0), "memory": (0.0, 0.5)})
    assert "closure" in env
    assert "memory" in env
    assert env.bounds["closure"] == (0.0, 1.0)
    assert env.bounds["memory"] == (0.0, 0.5)


def test_evaluate_inside_profile_returns_inside_verdict() -> None:
    env = Envelope(bounds={"closure": (0.0, 1.0)})
    result = env.evaluate(_profile(closure=0.5, memory=None))
    assert isinstance(result, ContainmentResult)
    assert result.verdict == ContainmentVerdict.INSIDE


def test_evaluate_outside_profile_returns_outside_verdict() -> None:
    env = Envelope(bounds={"closure": (0.0, 0.5)})
    result = env.evaluate(_profile(closure=0.9))
    assert result.verdict == ContainmentVerdict.OUTSIDE
    assert result.violated_axes == ("closure",)


def test_evaluate_undefined_axis_returns_undefined_verdict() -> None:
    env = Envelope(bounds={"closure": (0.0, 1.0)})
    result = env.evaluate(_profile(closure=None))
    assert result.verdict == ContainmentVerdict.UNDEFINED
    assert result.undefined_axes == ("closure",)


def test_envelope_from_trajectory_smoke() -> None:
    traj = ProfileTrajectory(axes=("closure", "memory"))
    for c, m in [(0.4, 0.2), (0.5, 0.3), (0.6, 0.4)]:
        traj.append(_profile(closure=c, memory=m))
    env = Envelope.from_trajectory(traj, width_multiplier=2.0)
    assert "closure" in env
    assert "memory" in env


def test_evaluate_accepts_mapping_input() -> None:
    env = Envelope(bounds={"closure": (0.0, 1.0)})
    result = env.evaluate({"closure": 0.5})
    assert result.verdict == ContainmentVerdict.INSIDE


def test_contains_shortcut_returns_bool() -> None:
    env = Envelope(bounds={"closure": (0.0, 1.0)})
    assert env.contains(_profile(closure=0.5)) is True
    assert env.contains(_profile(closure=2.0)) is False
    assert env.contains(_profile(closure=None)) is False


def test_envelope_rejects_invalid_bounds_lo_gt_hi() -> None:
    with pytest.raises(ValueError):
        Envelope(bounds={"closure": (0.5, 0.1)})


def test_envelope_rejects_non_finite_bounds() -> None:
    with pytest.raises(ValueError):
        Envelope(bounds={"closure": (0.0, float("inf"))})

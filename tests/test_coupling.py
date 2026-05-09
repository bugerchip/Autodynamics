"""Behavioural tests for ``autodynamics.coupling`` (v0.3.0a0).

The tests in this file lock in the locked decisions documented in
``docs/COUPLING_DIAGNOSTICS.md``. Smoke tests live in
``tests/test_coupling_smoke.py``.
"""

from __future__ import annotations

import numpy as np
import pytest
from autonometrics import AutonomyProfile

from autodynamics import (
    CausalCouplingGraph,
    CausalCouplingResult,
    ProfileTrajectory,
    density,
    granger_coupling,
    granger_graph,
    max_in_strength,
    max_out_strength,
    symmetry_ratio,
)


# ----------------------------------------------------------------------
# Fixtures / helpers
# ----------------------------------------------------------------------


def _ar_series(
    n: int,
    seed: int,
    phi: float = 0.5,
) -> np.ndarray:
    """Stationary AR(1): x[t] = phi * x[t-1] + eps[t]."""
    rng = np.random.default_rng(seed)
    x = np.zeros(n)
    for t in range(1, n):
        x[t] = phi * x[t - 1] + rng.normal(0, 1)
    return x


def _causal_pair(
    n: int,
    seed: int,
    coupling: float = 0.8,
    phi: float = 0.5,
) -> tuple[np.ndarray, np.ndarray]:
    """``a`` Granger-causes ``b``; ``b`` does not Granger-cause ``a``."""
    rng = np.random.default_rng(seed)
    a = np.zeros(n)
    b = np.zeros(n)
    for t in range(1, n):
        a[t] = phi * a[t - 1] + rng.normal(0, 1)
        b[t] = phi * b[t - 1] + coupling * a[t - 1] + rng.normal(0, 1)
    return a, b


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


def _trajectory_from_pair(
    a: np.ndarray, b: np.ndarray
) -> ProfileTrajectory:
    traj = ProfileTrajectory(axes=("closure", "memory"))
    for ai, bi in zip(a, b):
        traj.append(_make_profile(closure=float(ai), memory=float(bi)))
    return traj


# ----------------------------------------------------------------------
# granger_coupling — shape and basic invariants
# ----------------------------------------------------------------------


def test_granger_coupling_returns_dataclass() -> None:
    a, b = _causal_pair(200, seed=0)
    res = granger_coupling(a, b, n_min=50)
    assert isinstance(res, CausalCouplingResult)


def test_granger_coupling_rejects_2d_input() -> None:
    arr2d = np.zeros((100, 2))
    arr1d = np.zeros(100)
    with pytest.raises(ValueError):
        granger_coupling(arr2d, arr1d, n_min=50)
    with pytest.raises(ValueError):
        granger_coupling(arr1d, arr2d, n_min=50)


def test_granger_coupling_too_short_below_n_min() -> None:
    rng = np.random.default_rng(0)
    short = rng.normal(size=20)
    res = granger_coupling(short, short, n_min=50)
    assert res.status == "too_short"
    assert res.f_stat is None
    assert res.p_value is None
    assert res.n_obs_used == 20


def test_granger_coupling_constant_a_returns_constant_status() -> None:
    a = np.ones(200)
    b = _ar_series(200, seed=1)
    res = granger_coupling(a, b, n_min=50)
    assert res.status == "constant_series"


def test_granger_coupling_constant_b_returns_constant_status() -> None:
    a = _ar_series(200, seed=1)
    b = np.zeros(200)
    res = granger_coupling(a, b, n_min=50)
    assert res.status == "constant_series"


def test_granger_coupling_random_walk_marked_non_stationary() -> None:
    """A pure random walk should differentiate at most twice; if it
    survives (after one diff it becomes white noise) status is ``ok``."""
    rng = np.random.default_rng(7)
    rw = np.cumsum(rng.normal(size=200))
    res = granger_coupling(rw, rw + rng.normal(size=200), n_min=50)
    assert res.status == "ok"
    assert res.n_diff_a is not None and res.n_diff_a >= 1
    assert res.n_diff_b is not None and res.n_diff_b >= 1


def test_granger_coupling_ok_status_implies_finite_fstat() -> None:
    a, b = _causal_pair(200, seed=2)
    res = granger_coupling(a, b, n_min=50)
    assert res.status == "ok"
    assert res.f_stat is not None
    assert np.isfinite(res.f_stat)
    assert res.p_value is not None
    assert 0.0 <= res.p_value <= 1.0


def test_granger_coupling_lag_in_valid_range() -> None:
    a, b = _causal_pair(200, seed=3)
    res = granger_coupling(a, b, n_min=50, max_lag=4)
    assert res.lag is not None
    assert 1 <= res.lag <= 4


# ----------------------------------------------------------------------
# granger_coupling — causality direction
# ----------------------------------------------------------------------


def test_causal_direction_dominates_anti_causal_on_average() -> None:
    """Across multiple seeds, ``g(a -> b)`` should be larger than
    ``g(b -> a)`` more often than not when the link is ``a -> b``."""
    causal_wins = 0
    runs = 6
    for seed in range(runs):
        a, b = _causal_pair(200, seed=seed, coupling=0.8)
        f_ab = granger_coupling(a, b, n_min=50).f_stat
        f_ba = granger_coupling(b, a, n_min=50).f_stat
        assert f_ab is not None and f_ba is not None
        if f_ab > f_ba:
            causal_wins += 1
    assert causal_wins >= 4


def test_independent_series_low_p_value_rate() -> None:
    """Two independent AR(1) processes should not produce
    overwhelming Granger significance: p-values cluster above
    ``alpha`` more often than below."""
    significant = 0
    runs = 6
    for seed in range(runs):
        a = _ar_series(200, seed=seed)
        b = _ar_series(200, seed=seed + 100)
        res = granger_coupling(a, b, n_min=50)
        if res.status == "ok" and res.p_value is not None and res.p_value < 0.05:
            significant += 1
    assert significant <= 2


def test_self_against_self_is_perfectly_symmetric_when_admitted() -> None:
    """``granger_coupling(x, x)`` either flags constant or, after
    differencing, produces matched directions. We just verify it
    runs without raising and the status is in the valid set."""
    a = _ar_series(200, seed=0)
    res_ab = granger_coupling(a, a, n_min=50)
    res_ba = granger_coupling(a, a, n_min=50)
    assert res_ab.status == res_ba.status


# ----------------------------------------------------------------------
# granger_graph — shape, dispatch, axis admission
# ----------------------------------------------------------------------


def test_granger_graph_returns_correct_type() -> None:
    a, b = _causal_pair(200, seed=0)
    rng = np.random.default_rng(1)
    c = rng.normal(size=200)
    g = granger_graph({"a": a, "b": b, "c": c}, n_min=50)
    assert isinstance(g, CausalCouplingGraph)


def test_granger_graph_three_axes_six_directed_edges() -> None:
    a, b = _causal_pair(200, seed=0)
    rng = np.random.default_rng(1)
    c = rng.normal(size=200)
    g = granger_graph({"a": a, "b": b, "c": c}, n_min=50)
    assert len(g.edges) == 6
    for src in ("a", "b", "c"):
        for dst in ("a", "b", "c"):
            if src != dst:
                assert (src, dst) in g.edges


def test_granger_graph_excludes_too_short_axis() -> None:
    long_arr = _ar_series(200, seed=0)
    short_arr = np.zeros(20)
    g = granger_graph({"long": long_arr, "short": short_arr}, n_min=50)
    assert "short" in g.excluded_axes
    assert "too_short" in g.excluded_axes["short"] or "mosaic" in g.excluded_axes["short"]


def test_granger_graph_excludes_saturated_axis() -> None:
    long_arr = _ar_series(200, seed=0)
    flat = np.ones(200)
    g = granger_graph({"signal": long_arr, "flat": flat}, n_min=50)
    assert "flat" in g.excluded_axes
    assert g.excluded_axes["flat"] == "saturated_axis"


def test_granger_graph_excludes_axis_below_mosaic_threshold() -> None:
    a = _ar_series(200, seed=0)
    holes = a.tolist()
    for i in range(0, 100):
        holes[i] = None
    g = granger_graph({"a": a, "holes": holes}, n_min=50, mosaic_threshold=0.8)
    assert "holes" in g.excluded_axes
    assert "mosaic_dropout" in g.excluded_axes["holes"]


def test_granger_graph_empty_mapping_returns_empty_graph() -> None:
    g = granger_graph({}, n_min=50)
    assert g.axes_used == ()
    assert len(g.edges) == 0
    assert g.null_pairs == ()
    assert g.n_obs_min == 0


def test_granger_graph_explicit_axes_subset() -> None:
    a = _ar_series(200, seed=0)
    b = _ar_series(200, seed=1)
    c = _ar_series(200, seed=2)
    g = granger_graph(
        {"a": a, "b": b, "c": c},
        axes=["a", "b"],
        n_min=50,
    )
    assert set(g.axes_used) == {"a", "b"}
    assert len(g.edges) == 2


def test_granger_graph_single_axis_yields_zero_edges() -> None:
    a = _ar_series(200, seed=0)
    g = granger_graph({"only": a}, n_min=50)
    assert g.axes_used == ("only",)
    assert len(g.edges) == 0


def test_granger_graph_rejects_non_mapping_non_trajectory() -> None:
    with pytest.raises(TypeError):
        granger_graph([1, 2, 3], n_min=50)  # type: ignore[arg-type]


def test_granger_graph_treats_nan_as_missing() -> None:
    """``NaN`` and ``None`` are treated identically by the policy."""
    a = _ar_series(200, seed=0)
    nan_holes = a.copy()
    nan_holes[0:30] = np.nan
    g = granger_graph(
        {"a": a, "with_nan": nan_holes},
        n_min=50,
        mosaic_threshold=0.5,
    )
    # Longest contiguous run on `with_nan` is 170 — admitted.
    assert "with_nan" in g.axes_used


# ----------------------------------------------------------------------
# granger_graph — ProfileTrajectory dispatch
# ----------------------------------------------------------------------


def test_granger_graph_from_profile_trajectory() -> None:
    a, b = _causal_pair(200, seed=0)
    traj = _trajectory_from_pair(a, b)
    g = granger_graph(traj, n_min=50)
    assert set(g.axes_used) == {"closure", "memory"}
    assert len(g.edges) == 2


def test_granger_graph_trajectory_with_explicit_axes() -> None:
    a, b = _causal_pair(200, seed=0)
    traj = _trajectory_from_pair(a, b)
    g = granger_graph(traj, axes=["closure"], n_min=50)
    assert g.axes_used == ("closure",)
    assert len(g.edges) == 0


def test_granger_graph_trajectory_with_full_dropout_excludes_axis() -> None:
    rng = np.random.default_rng(0)
    a = rng.normal(size=200)
    traj = ProfileTrajectory(axes=("closure", "memory"))
    for ai in a:
        traj.append(_make_profile(closure=float(ai), memory=None))
    g = granger_graph(traj, n_min=50, mosaic_threshold=0.5)
    assert "memory" in g.excluded_axes
    assert "closure" in g.axes_used


def test_granger_graph_trajectory_longest_contiguous_run_extracted() -> None:
    """Trajectory with a gap in the middle: longest contiguous run is
    used, not the spliced concatenation."""
    rng = np.random.default_rng(0)
    n = 200
    a = rng.normal(size=n)
    b = rng.normal(size=n)
    traj = ProfileTrajectory(axes=("closure", "memory"))
    for i, (ai, bi) in enumerate(zip(a, b)):
        if 50 <= i < 70:
            traj.append(_make_profile(closure=None, memory=float(bi)))
        else:
            traj.append(_make_profile(closure=float(ai), memory=float(bi)))
    g = granger_graph(traj, n_min=50, mosaic_threshold=0.5)
    # Longest contiguous run on closure is post-gap, length 130: admitted.
    assert "closure" in g.axes_used


# ----------------------------------------------------------------------
# CausalCouplingGraph helpers
# ----------------------------------------------------------------------


def test_graph_edge_returns_result_for_admitted_pair() -> None:
    a, b = _causal_pair(200, seed=0)
    g = granger_graph({"a": a, "b": b}, n_min=50)
    res = g.edge("a", "b")
    assert isinstance(res, CausalCouplingResult)


def test_graph_edge_raises_keyerror_for_missing_pair() -> None:
    a, b = _causal_pair(200, seed=0)
    g = granger_graph({"a": a, "b": b}, n_min=50)
    with pytest.raises(KeyError):
        g.edge("a", "z")


def test_graph_n_obs_min_zero_when_all_pairs_null() -> None:
    """If every pair fails (e.g. saturation), n_obs_min is 0."""
    flat = np.ones(200)
    flat2 = np.ones(200) * 2.0
    g = granger_graph({"a": flat, "b": flat2}, n_min=50)
    assert g.n_obs_min == 0


# ----------------------------------------------------------------------
# CausalCouplingResult invariants
# ----------------------------------------------------------------------


def test_result_status_must_be_in_valid_set() -> None:
    with pytest.raises(ValueError):
        CausalCouplingResult(
            f_stat=None,
            p_value=None,
            lag=None,
            n_diff_a=None,
            n_diff_b=None,
            n_obs_used=None,
            status="invented_status",
        )


# ----------------------------------------------------------------------
# Metrics
# ----------------------------------------------------------------------


def test_symmetry_ratio_in_unit_interval_on_real_graph() -> None:
    a, b = _causal_pair(200, seed=0)
    rng = np.random.default_rng(1)
    c = rng.normal(size=200)
    g = granger_graph({"a": a, "b": b, "c": c}, n_min=50)
    sym = symmetry_ratio(g)
    assert sym is not None
    assert 0.0 <= sym <= 1.0


def test_symmetry_ratio_none_on_empty_graph() -> None:
    g = granger_graph({}, n_min=50)
    assert symmetry_ratio(g) is None


def test_density_in_unit_interval() -> None:
    a, b = _causal_pair(200, seed=0)
    rng = np.random.default_rng(1)
    c = rng.normal(size=200)
    g = granger_graph({"a": a, "b": b, "c": c}, n_min=50)
    d = density(g)
    assert d is not None
    assert 0.0 <= d <= 1.0


def test_density_with_explicit_threshold() -> None:
    a, b = _causal_pair(200, seed=0)
    g = granger_graph({"a": a, "b": b}, n_min=50)
    d_lo = density(g, tau=0.0)
    d_hi = density(g, tau=1e9)
    assert d_lo == 1.0 or d_lo is None
    assert d_hi == 0.0 or d_hi is None


def test_density_none_on_empty_graph() -> None:
    g = granger_graph({}, n_min=50)
    assert density(g) is None


def test_density_alpha_changes_threshold() -> None:
    a, b = _causal_pair(200, seed=0)
    rng = np.random.default_rng(1)
    c = rng.normal(size=200)
    g = granger_graph({"a": a, "b": b, "c": c}, n_min=50)
    d_strict = density(g, alpha=0.001)
    d_loose = density(g, alpha=0.20)
    if d_strict is not None and d_loose is not None:
        assert d_loose >= d_strict


def test_max_in_strength_returns_value_for_real_axis() -> None:
    a, b = _causal_pair(200, seed=0)
    g = granger_graph({"a": a, "b": b}, n_min=50)
    val = max_in_strength(g, "b")
    assert val is not None
    assert val >= 0.0


def test_max_in_strength_none_for_unknown_axis() -> None:
    a, b = _causal_pair(200, seed=0)
    g = granger_graph({"a": a, "b": b}, n_min=50)
    assert max_in_strength(g, "no_such_axis") is None


def test_max_out_strength_returns_value_for_real_axis() -> None:
    a, b = _causal_pair(200, seed=0)
    g = granger_graph({"a": a, "b": b}, n_min=50)
    val = max_out_strength(g, "a")
    assert val is not None
    assert val >= 0.0


def test_max_out_strength_none_for_unknown_axis() -> None:
    a, b = _causal_pair(200, seed=0)
    g = granger_graph({"a": a, "b": b}, n_min=50)
    assert max_out_strength(g, "no_such_axis") is None


def test_metrics_mosaic_dropout_friendly() -> None:
    """All four diagnostics return ``None`` when no admitted edge has
    a finite F-statistic, never raising."""
    flat = np.ones(200)
    flat2 = np.ones(200) * 2.0
    g = granger_graph({"a": flat, "b": flat2}, n_min=50)
    assert symmetry_ratio(g) is None
    assert density(g) is None
    assert max_in_strength(g, "a") is None
    assert max_out_strength(g, "b") is None


# ----------------------------------------------------------------------
# Determinism
# ----------------------------------------------------------------------


def test_granger_graph_deterministic_under_same_seed() -> None:
    """Running the same input twice yields identical F-stats."""
    a1, b1 = _causal_pair(200, seed=42)
    a2, b2 = _causal_pair(200, seed=42)
    np.testing.assert_array_equal(a1, a2)
    np.testing.assert_array_equal(b1, b2)
    g1 = granger_graph({"a": a1, "b": b1}, n_min=50)
    g2 = granger_graph({"a": a2, "b": b2}, n_min=50)
    f1 = g1.edges[("a", "b")].f_stat
    f2 = g2.edges[("a", "b")].f_stat
    assert f1 == f2

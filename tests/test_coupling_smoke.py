"""Smoke tests for ``autodynamics.coupling``.

Minimal sanity checks: imports, return shapes, and a couple of
deterministic synthetic cases. Full behavioural coverage lives in
``tests/test_coupling.py`` (added later in the cycle alongside
``docs/COUPLING_DIAGNOSTICS.md``).
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


def _ar_series_with_causal_link(
    n: int = 200,
    coupling_strength: float = 0.8,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Generate ``(a, b)`` where ``a`` Granger-causes ``b``.

    Both series are AR(1) plus the causal link ``b[t] += k * a[t-1]``.
    """
    rng = np.random.default_rng(seed)
    a = np.zeros(n)
    b = np.zeros(n)
    for t in range(1, n):
        a[t] = 0.5 * a[t - 1] + rng.normal(0, 1)
        b[t] = (
            0.5 * b[t - 1]
            + coupling_strength * a[t - 1]
            + rng.normal(0, 1)
        )
    return a, b


def _make_profile(
    closure: float | None = None,
    memory: float | None = None,
) -> AutonomyProfile:
    return AutonomyProfile(
        ratio_endo_total=closure,
        memory_endo_ratio=memory,
    )


def test_imports_top_level_and_submodule() -> None:
    """All public symbols import from both `autodynamics` and `autodynamics.coupling`."""
    from autodynamics import coupling  # noqa: PLC0415

    assert hasattr(coupling, "granger_coupling")
    assert hasattr(coupling, "granger_graph")
    assert hasattr(coupling, "CausalCouplingGraph")
    assert hasattr(coupling, "CausalCouplingResult")
    assert hasattr(coupling, "symmetry_ratio")
    assert hasattr(coupling, "density")
    assert hasattr(coupling, "max_in_strength")
    assert hasattr(coupling, "max_out_strength")


def test_granger_coupling_returns_result_on_causal_pair() -> None:
    """A clearly causal AR pair returns a finite F-stat in the causal direction."""
    a, b = _ar_series_with_causal_link(n=200, coupling_strength=0.8, seed=1)
    res_ab = granger_coupling(a, b, n_min=50)
    assert isinstance(res_ab, CausalCouplingResult)
    assert res_ab.status == "ok"
    assert res_ab.f_stat is not None
    assert res_ab.f_stat > 0.0
    assert res_ab.p_value is not None
    assert 0.0 <= res_ab.p_value <= 1.0


def test_granger_coupling_too_short_returns_status_too_short() -> None:
    rng = np.random.default_rng(0)
    short = rng.normal(size=20)
    res = granger_coupling(short, short, n_min=50)
    assert res.status == "too_short"
    assert res.f_stat is None
    assert res.p_value is None


def test_granger_coupling_constant_series_status() -> None:
    a = np.ones(200)
    b = np.linspace(0.0, 1.0, 200)
    res = granger_coupling(a, b, n_min=50)
    assert res.status == "constant_series"
    assert res.f_stat is None


def test_granger_graph_from_dict() -> None:
    """`granger_graph` accepts a mapping of series and produces a directed graph."""
    a, b = _ar_series_with_causal_link(n=200, coupling_strength=0.8, seed=2)
    rng = np.random.default_rng(3)
    c = rng.normal(size=200)

    graph = granger_graph(
        {"a": a, "b": b, "c": c},
        n_min=50,
    )
    assert isinstance(graph, CausalCouplingGraph)
    assert set(graph.axes_used) == {"a", "b", "c"}
    # Six directed edges across three nodes.
    assert len(graph.edges) == 6
    # Causal direction has a finite F-stat.
    res_ab = graph.edges[("a", "b")]
    assert res_ab.f_stat is not None


def test_granger_graph_drops_too_short_axis() -> None:
    rng = np.random.default_rng(0)
    long_series = rng.normal(size=200)
    short_series = rng.normal(size=10)

    graph = granger_graph(
        {"keep": long_series, "drop": short_series},
        n_min=50,
        mosaic_threshold=0.0,
    )
    assert "keep" in graph.axes_used
    assert "drop" not in graph.axes_used
    assert "drop" in graph.excluded_axes


def test_granger_graph_from_profile_trajectory() -> None:
    """`granger_graph` accepts a `ProfileTrajectory` directly."""
    a, b = _ar_series_with_causal_link(n=200, coupling_strength=0.8, seed=4)
    traj = ProfileTrajectory(axes=("closure", "memory"))
    for ai, bi in zip(a, b):
        traj.append(_make_profile(closure=float(ai), memory=float(bi)))

    graph = granger_graph(traj, n_min=50)
    assert isinstance(graph, CausalCouplingGraph)
    assert set(graph.axes_used) == {"closure", "memory"}
    assert len(graph.edges) == 2


def test_granger_graph_handles_none_in_trajectory() -> None:
    """Mosaic-dropout in a trajectory yields longest-contiguous-run handling."""
    rng = np.random.default_rng(5)
    a = rng.normal(size=200)
    b = rng.normal(size=200)
    traj = ProfileTrajectory(axes=("closure", "memory"))
    for i, (ai, bi) in enumerate(zip(a, b)):
        if 50 <= i < 70:
            traj.append(_make_profile(closure=None, memory=float(bi)))
        else:
            traj.append(_make_profile(closure=float(ai), memory=float(bi)))

    graph = granger_graph(traj, n_min=50, mosaic_threshold=0.5)
    assert isinstance(graph, CausalCouplingGraph)
    # Longest contiguous run on `closure` is post-gap, length 130: admitted.
    assert "closure" in graph.axes_used
    assert "memory" in graph.axes_used


def test_metrics_return_shapes_on_real_graph() -> None:
    a, b = _ar_series_with_causal_link(n=200, coupling_strength=0.8, seed=6)
    rng = np.random.default_rng(7)
    c = rng.normal(size=200)
    graph = granger_graph({"a": a, "b": b, "c": c}, n_min=50)

    sym = symmetry_ratio(graph)
    dens = density(graph)
    max_in_b = max_in_strength(graph, "b")
    max_out_a = max_out_strength(graph, "a")

    if sym is not None:
        assert 0.0 <= sym <= 1.0
    if dens is not None:
        assert 0.0 <= dens <= 1.0
    if max_in_b is not None:
        assert max_in_b >= 0.0
    if max_out_a is not None:
        assert max_out_a >= 0.0


def test_metrics_return_none_on_empty_graph() -> None:
    """Diagnostics return `None` when the graph has no usable edges."""
    graph = granger_graph({}, n_min=50)
    assert graph.axes_used == ()
    assert symmetry_ratio(graph) is None
    assert density(graph) is None
    assert max_in_strength(graph, "anything") is None
    assert max_out_strength(graph, "anything") is None


def test_granger_graph_rejects_non_mapping_non_trajectory() -> None:
    with pytest.raises(TypeError):
        granger_graph([1, 2, 3], n_min=50)  # type: ignore[arg-type]

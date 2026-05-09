"""Scalar diagnostics over a :class:`CausalCouplingGraph`.

Four convenience aggregates over the directed Granger-causal graph:

- :func:`symmetry_ratio`: pairwise symmetry of the F-statistic.
- :func:`density`: fraction of edges above an F-statistic threshold.
- :func:`max_in_strength`: strongest incoming edge for an axis.
- :func:`max_out_strength`: strongest outgoing edge for an axis.

All four return ``None`` whenever the underlying graph has no usable
edges, mirroring the mosaic-dropout policy of the rest of
``autodynamics``.
"""

from __future__ import annotations

import numpy as np

from autodynamics.coupling.graph import CausalCouplingGraph
from autodynamics.coupling.granger import DEFAULT_ALPHA


def symmetry_ratio(graph: CausalCouplingGraph) -> float | None:
    """Pairwise F-statistic symmetry, averaged over usable pairs.

    For each unordered pair ``{a, b}``::

        ratio(a, b) = min(g(a -> b), g(b -> a)) / max(g(a -> b), g(b -> a))

    The aggregate is the arithmetic mean over pairs where both
    directions returned a finite F-stat. Returns ``None`` if no
    usable pair exists.

    A value near ``1.0`` indicates roughly symmetric coupling
    (no clear directional dominance); a value near ``0.0`` indicates
    a strongly asymmetric coupling structure.
    """
    axes = list(graph.axes_used)
    ratios: list[float] = []
    for i, a in enumerate(axes):
        for b in axes[i + 1 :]:
            f_ab = graph.edges.get((a, b))
            f_ba = graph.edges.get((b, a))
            if f_ab is None or f_ba is None:
                continue
            if f_ab.f_stat is None or f_ba.f_stat is None:
                continue
            mn = min(f_ab.f_stat, f_ba.f_stat)
            mx = max(f_ab.f_stat, f_ba.f_stat)
            if mx <= 0.0:
                continue
            ratios.append(float(mn) / float(mx))

    if not ratios:
        return None
    return float(np.mean(ratios))


def density(
    graph: CausalCouplingGraph,
    *,
    tau: float | None = None,
    alpha: float = DEFAULT_ALPHA,
) -> float | None:
    """Fraction of edges whose F-stat exceeds threshold ``tau``.

    If ``tau`` is ``None``, the per-edge F critical value at the
    given ``alpha`` is used, computed from the lag actually selected
    for that edge and its effective sample size. Returns ``None`` if
    the graph has no usable edges.

    Parameters
    ----------
    graph:
        The causal coupling graph to summarise.
    tau:
        Optional explicit F-statistic threshold. When ``None``
        (default), the threshold is the F critical value at level
        ``alpha`` for the per-edge degrees of freedom.
    alpha:
        Significance level for the implicit threshold. Ignored when
        ``tau`` is provided. Default ``0.05``.
    """
    from scipy.stats import f as f_dist

    edges_total = 0
    edges_above = 0

    for res in graph.edges.values():
        if res.f_stat is None:
            continue
        edges_total += 1

        if tau is not None:
            edge_tau = float(tau)
        else:
            lag = res.lag if res.lag and res.lag > 0 else 1
            n = res.n_obs_used if res.n_obs_used else 0
            df1 = lag
            df2 = n - 2 * lag - 1
            if df2 <= 0:
                continue
            edge_tau = float(f_dist.ppf(1.0 - alpha, df1, df2))

        if res.f_stat > edge_tau:
            edges_above += 1

    if edges_total == 0:
        return None
    return float(edges_above) / float(edges_total)


def max_in_strength(graph: CausalCouplingGraph, axis: str) -> float | None:
    """Maximum incoming F-statistic for ``axis``.

    "Incoming" means edges of the form ``a -> axis`` for any
    ``a != axis`` that returned a finite F-stat. Returns ``None``
    if no incoming edge has a usable F-stat.
    """
    incoming: list[float] = []
    for (_a, b), res in graph.edges.items():
        if b != axis or res.f_stat is None:
            continue
        incoming.append(float(res.f_stat))
    if not incoming:
        return None
    return float(max(incoming))


def max_out_strength(graph: CausalCouplingGraph, axis: str) -> float | None:
    """Maximum outgoing F-statistic for ``axis``.

    "Outgoing" means edges of the form ``axis -> b`` for any
    ``b != axis`` that returned a finite F-stat. Returns ``None``
    if no outgoing edge has a usable F-stat.
    """
    outgoing: list[float] = []
    for (a, _b), res in graph.edges.items():
        if a != axis or res.f_stat is None:
            continue
        outgoing.append(float(res.f_stat))
    if not outgoing:
        return None
    return float(max(outgoing))

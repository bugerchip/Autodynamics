"""Granger-causal coupling analysis over autonomy-profile trajectories.

Public API:

- :class:`CausalCouplingResult` — outcome of a single pairwise Granger
  test, with F-statistic, p-value, selected lag, differencing counts,
  effective sample size, and status.
- :class:`CausalCouplingGraph` — directed causal coupling graph over a
  set of axes, with bookkeeping for admitted / excluded axes and null
  pairs.
- :func:`granger_coupling` — pairwise primitive: directional Granger
  coupling between two one-dimensional series.
- :func:`granger_graph` — graph-level entry point: build the directed
  coupling graph from a :class:`autodynamics.ProfileTrajectory` or a
  mapping ``{axis_name: series}``.
- :func:`symmetry_ratio`, :func:`density`, :func:`max_in_strength`,
  :func:`max_out_strength` — scalar diagnostics over the graph.

All routines respect the mosaic-dropout policy of ``autodynamics``:
``None`` (or ``NaN``) values trigger longest-contiguous-subseries
extraction inside each axis; pairs whose F-statistic cannot be
computed are recorded as null pairs and excluded from aggregates.

The full protocol (admission rules, stationarity gate, lag selection,
F-test) is pre-registered in ``docs/COUPLING_DIAGNOSTICS.md``.

References:

- Granger, C. W. J. (1969). "Investigating Causal Relations by
  Econometric Models and Cross-spectral Methods." *Econometrica*
  37 (3): 424-438.
- Sims, C. A. (1980). "Macroeconomics and Reality." *Econometrica*
  48 (1): 1-48.
- Lutkepohl, H. (2005). *New Introduction to Multiple Time Series
  Analysis*. Springer.
"""

from autodynamics.coupling.graph import (
    CausalCouplingGraph,
    granger_graph,
)
from autodynamics.coupling.granger import (
    CausalCouplingResult,
    granger_coupling,
)
from autodynamics.coupling.metrics import (
    density,
    max_in_strength,
    max_out_strength,
    symmetry_ratio,
)

__all__ = [
    "CausalCouplingGraph",
    "CausalCouplingResult",
    "density",
    "granger_coupling",
    "granger_graph",
    "max_in_strength",
    "max_out_strength",
    "symmetry_ratio",
]

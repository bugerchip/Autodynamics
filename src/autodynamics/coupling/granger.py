"""Granger causality between two series (pairwise primitive).

Implements pairwise directional Granger causality between two
one-dimensional series, following the standard convention:

    g(a -> b) = F-statistic of the Granger test asking whether past
    lags of ``a`` improve the prediction of ``b`` beyond ``b``'s own
    lags.

The implementation follows the protocol pre-registered in
``docs/COUPLING_DIAGNOSTICS.md``:

- Step 1: drop pairs with insufficient effective sample size.
- Step 2: enforce stationarity via ADF (Augmented Dickey-Fuller),
  differentiating up to twice if the level-series is non-stationary.
- Step 3: fit a bivariate VAR model.
- Step 4: select the lag order by AIC.
- Step 5: run the F-test for Granger causality on the selected lag.

References:

- Granger, C. W. J. (1969). "Investigating Causal Relations by
  Econometric Models and Cross-spectral Methods." *Econometrica*
  37 (3): 424-438.
- Sims, C. A. (1980). "Macroeconomics and Reality." *Econometrica*
  48 (1): 1-48.
- Lutkepohl, H. (2005). *New Introduction to Multiple Time Series
  Analysis*. Springer.
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


_VALID_STATUSES = (
    "ok",
    "too_short",
    "constant_series",
    "non_stationary",
    "var_failed",
    "ftest_failed",
)


@dataclass(frozen=True)
class CausalCouplingResult:
    """Outcome of a single :func:`granger_coupling` call.

    Attributes
    ----------
    f_stat:
        F-statistic of the Granger test in the direction ``a -> b``.
        ``None`` whenever the computation cannot complete validly.
    p_value:
        Associated p-value, ``None`` whenever ``f_stat`` is ``None``.
    lag:
        VAR lag actually selected by AIC.
    n_diff_a, n_diff_b:
        Number of differences applied to each series to achieve
        stationarity. ``0`` means the original series passed ADF.
    n_obs_used:
        Effective sample size used by the VAR after differencing and
        alignment.
    status:
        One of ``ok``, ``too_short``, ``constant_series``,
        ``non_stationary``, ``var_failed``, ``ftest_failed``.
    message:
        Human-readable diagnostic when ``status != "ok"``.
    """

    f_stat: float | None
    p_value: float | None
    lag: int | None
    n_diff_a: int | None
    n_diff_b: int | None
    n_obs_used: int | None
    status: str
    message: str | None = None

    def __post_init__(self) -> None:
        if self.status not in _VALID_STATUSES:
            raise ValueError(
                f"status must be one of {_VALID_STATUSES}; got {self.status!r}"
            )


# Defaults aligned with the protocol in ``docs/COUPLING_DIAGNOSTICS.md``.
DEFAULT_MAX_LAG = 6
DEFAULT_N_MIN = 50
DEFAULT_ALPHA = 0.05
_MAX_DIFFS = 2
_CONSTANT_TOL = 1e-12


def _is_constant(series: np.ndarray) -> bool:
    if series.size == 0:
        return True
    return float(np.std(series)) < _CONSTANT_TOL


def _ensure_stationary(series: np.ndarray) -> tuple[int, np.ndarray]:
    """Apply ADF; differentiate up to twice if non-stationary.

    Returns ``(n_diffs_applied, transformed_series)``. If the series
    remains non-stationary after the cap, returns
    ``(_MAX_DIFFS + 1, ...)`` to signal failure to the caller.
    """
    from statsmodels.tsa.stattools import adfuller

    s = np.asarray(series, dtype=np.float64)

    for n_diff in range(_MAX_DIFFS + 1):
        if _is_constant(s):
            return n_diff, s

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                p = float(adfuller(s, autolag="AIC")[1])
        except Exception:
            return n_diff, s

        if p < DEFAULT_ALPHA:
            return n_diff, s

        if n_diff < _MAX_DIFFS:
            s = np.diff(s)

    return _MAX_DIFFS + 1, s


def granger_coupling(
    x_a: Sequence[float] | np.ndarray,
    x_b: Sequence[float] | np.ndarray,
    *,
    max_lag: int = DEFAULT_MAX_LAG,
    n_min: int = DEFAULT_N_MIN,
) -> CausalCouplingResult:
    """Compute the directional Granger coupling ``g(a -> b)``.

    Following the standard convention, ``g(a -> b)`` measures the
    strength with which past values of ``a`` improve prediction of
    ``b``. Higher values mean ``a`` Granger-causes ``b`` more strongly.

    Parameters
    ----------
    x_a, x_b:
        One-dimensional float sequences of length at least ``n_min``.
        ``None`` / ``NaN`` values are not handled here; the caller is
        responsible for providing dropout-clean inputs (see
        :func:`autodynamics.coupling.granger_graph` for the
        trajectory-aware wrapper).
    max_lag:
        Maximum VAR lag for AIC selection. Default ``6``.
    n_min:
        Minimum admissible series length. Default ``50``.

    Returns
    -------
    CausalCouplingResult
        Result record with F-statistic, p-value, selected lag,
        differencing counts, effective sample size, and status.
    """
    a = np.asarray(x_a, dtype=np.float64)
    b = np.asarray(x_b, dtype=np.float64)

    if a.ndim != 1 or b.ndim != 1:
        raise ValueError("x_a and x_b must be one-dimensional sequences")

    if a.size < n_min or b.size < n_min:
        return CausalCouplingResult(
            f_stat=None,
            p_value=None,
            lag=None,
            n_diff_a=None,
            n_diff_b=None,
            n_obs_used=int(min(a.size, b.size)),
            status="too_short",
            message=(
                f"length(a)={a.size}, length(b)={b.size}; both must be >= {n_min}"
            ),
        )

    if _is_constant(a) or _is_constant(b):
        return CausalCouplingResult(
            f_stat=None,
            p_value=None,
            lag=None,
            n_diff_a=None,
            n_diff_b=None,
            n_obs_used=None,
            status="constant_series",
            message="At least one input series has zero variance.",
        )

    n_diff_a, a_stat = _ensure_stationary(a)
    n_diff_b, b_stat = _ensure_stationary(b)

    if n_diff_a > _MAX_DIFFS or n_diff_b > _MAX_DIFFS:
        return CausalCouplingResult(
            f_stat=None,
            p_value=None,
            lag=None,
            n_diff_a=n_diff_a,
            n_diff_b=n_diff_b,
            n_obs_used=None,
            status="non_stationary",
            message=(
                f"Series remained non-stationary after {_MAX_DIFFS} differences."
            ),
        )

    n = int(min(a_stat.size, b_stat.size))
    if n < n_min:
        return CausalCouplingResult(
            f_stat=None,
            p_value=None,
            lag=None,
            n_diff_a=n_diff_a,
            n_diff_b=n_diff_b,
            n_obs_used=n,
            status="too_short",
            message=(
                f"After differencing, n={n} < n_min={n_min}."
            ),
        )

    a_stat = a_stat[-n:]
    b_stat = b_stat[-n:]

    if _is_constant(a_stat) or _is_constant(b_stat):
        return CausalCouplingResult(
            f_stat=None,
            p_value=None,
            lag=None,
            n_diff_a=n_diff_a,
            n_diff_b=n_diff_b,
            n_obs_used=n,
            status="constant_series",
            message="A series became constant after differencing.",
        )

    from statsmodels.tsa.api import VAR

    data = np.column_stack([a_stat, b_stat])

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = VAR(data)
            order_results = model.select_order(maxlags=max_lag)
            lag_selected = int(getattr(order_results, "aic", 0) or 0)
            if lag_selected < 1:
                lag_selected = 1
            var_fit = model.fit(maxlags=lag_selected, ic=None, verbose=False)
    except Exception as exc:  # noqa: BLE001
        return CausalCouplingResult(
            f_stat=None,
            p_value=None,
            lag=None,
            n_diff_a=n_diff_a,
            n_diff_b=n_diff_b,
            n_obs_used=n,
            status="var_failed",
            message=str(exc),
        )

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            test_result = var_fit.test_causality(
                caused=1, causing=0, kind="f", signif=DEFAULT_ALPHA
            )
        f_stat = float(test_result.test_statistic)
        p_value = float(test_result.pvalue)
    except Exception as exc:  # noqa: BLE001
        return CausalCouplingResult(
            f_stat=None,
            p_value=None,
            lag=lag_selected,
            n_diff_a=n_diff_a,
            n_diff_b=n_diff_b,
            n_obs_used=n,
            status="ftest_failed",
            message=str(exc),
        )

    if not np.isfinite(f_stat):
        return CausalCouplingResult(
            f_stat=None,
            p_value=None,
            lag=lag_selected,
            n_diff_a=n_diff_a,
            n_diff_b=n_diff_b,
            n_obs_used=n,
            status="ftest_failed",
            message="F-stat not finite (likely degenerate residual variance).",
        )

    return CausalCouplingResult(
        f_stat=f_stat,
        p_value=p_value,
        lag=lag_selected,
        n_diff_a=n_diff_a,
        n_diff_b=n_diff_b,
        n_obs_used=n,
        status="ok",
    )

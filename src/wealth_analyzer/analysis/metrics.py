"""Performance metrics engine built on quantstats and scipy."""

from __future__ import annotations

import logging
from datetime import date

import numpy as np
import pandas as pd
import quantstats as qs
from scipy.optimize import brentq

logger = logging.getLogger(__name__)


def _npv(rate: float, cashflows: list[tuple[date, float]], t0: date) -> float:
    """Net present value of *cashflows* discounted at *rate*.

    Uses Actual/365 day-count convention relative to *t0*.
    """
    total = 0.0
    for t, cf in cashflows:
        years = (t - t0).days / 365.0
        total += cf / (1.0 + rate) ** years
    return total


def xirr(cashflows: list[tuple[date, float]]) -> float:
    """Compute the internal rate of return for irregular cash flows.

    Parameters
    ----------
    cashflows:
        List of ``(date, amount)`` tuples.  Investments are negative,
        withdrawals / terminal value are positive.

    Returns
    -------
    float
        The annualised IRR that makes NPV = 0.

    Raises
    ------
    ValueError
        If fewer than 2 cashflows, there is no sign change (all positive or
        all negative), or Brent's method fails to converge.
    """
    if len(cashflows) < 2:
        raise ValueError("xirr requires at least two cashflows")

    # Combine same-day cashflows
    by_day: dict[date, float] = {}
    for t, cf in cashflows:
        by_day[t] = by_day.get(t, 0.0) + cf
    combined = sorted(by_day.items())

    # Check for sign change
    values = [v for _, v in combined]
    has_positive = any(v > 0 for v in values)
    has_negative = any(v < 0 for v in values)
    if not (has_positive and has_negative):
        raise ValueError("no sign change in cashflows — cannot compute IRR")

    t0 = combined[0][0]

    def f(r: float) -> float:
        return _npv(r, combined, t0)

    try:
        return brentq(f, -0.9999, 10.0, xtol=1e-10, maxiter=1000)
    except ValueError as exc:
        raise ValueError(f"xirr did not converge: {exc}") from exc


def _log_to_simple(log_returns: pd.Series) -> pd.Series:
    """Convert log-returns to simple (percentage) returns."""
    return np.exp(log_returns) - 1.0


def _recovery_months(dd_details: pd.DataFrame) -> int | None:
    """Return months between worst drawdown start and recovery, or ``None``."""
    if dd_details.empty:
        return None

    worst_idx = dd_details["max drawdown"].idxmin()
    worst = dd_details.loc[worst_idx]

    end_date = worst["end"]
    valley_date = worst["valley"]
    start_date = worst["start"]

    if pd.isna(end_date) or pd.isna(start_date):
        return None

    # If end == valley, the drawdown never recovered (series ended in drawdown)
    if not pd.isna(valley_date) and end_date == valley_date:
        return None

    # Convert to Timestamp if needed
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)

    months = (end_ts.year - start_ts.year) * 12 + (end_ts.month - start_ts.month)
    return max(months, 1)


def compute_metrics(
    returns: pd.Series,
    prices: pd.Series,
    risk_free_rate: float,
) -> dict[str, float | str | None]:
    """Compute a standard set of performance metrics.

    Parameters
    ----------
    returns:
        Daily **log-returns** of the asset's adjusted-close series.
    prices:
        Adjusted-close price series (same index as *returns*).
    risk_free_rate:
        Annualised risk-free rate (e.g. ``0.045`` for 4.5 %).

    Returns
    -------
    dict
        Flat dict with keys:
        ``cagr``, ``sharpe``, ``sortino``, ``max_drawdown_pct``,
        ``max_drawdown_recovery_months``, ``annualized_volatility``,
        ``total_return_pct``, ``dividend_contribution_pct``.
    """
    empty_keys = [
        "cagr",
        "sharpe",
        "sortino",
        "max_drawdown_pct",
        "max_drawdown_recovery_months",
        "annualized_volatility",
        "total_return_pct",
        "dividend_contribution_pct",
    ]

    # Guard: empty or single-row input
    if returns.empty or len(returns) < 2:
        logger.warning("compute_metrics called with fewer than 2 rows — returning NaN")
        return {
            k: float("nan") if k != "max_drawdown_recovery_months" else None
            for k in empty_keys
        }

    # quantstats expects simple returns
    simple = _log_to_simple(returns)

    # --- CAGR -----------------------------------------------------------
    cagr = float(qs.stats.cagr(simple, rf=risk_free_rate, periods=252))

    # --- Sharpe ----------------------------------------------------------
    try:
        sharpe = float(qs.stats.sharpe(simple, rf=risk_free_rate, periods=252))
    except (ZeroDivisionError, FloatingPointError):
        sharpe = 0.0
    if not np.isfinite(sharpe):
        sharpe = 0.0

    # --- Sortino ---------------------------------------------------------
    try:
        sortino = float(qs.stats.sortino(simple, rf=risk_free_rate, periods=252))
    except (ZeroDivisionError, FloatingPointError):
        sortino = 0.0
    if not np.isfinite(sortino):
        sortino = 0.0

    # --- Max drawdown & recovery ----------------------------------------
    max_dd = float(qs.stats.max_drawdown(simple))

    dd_series = qs.stats.to_drawdown_series(simple)
    dd_details = qs.stats.drawdown_details(dd_series)
    recovery = _recovery_months(dd_details) if not dd_details.empty else None

    # --- Annualized volatility ------------------------------------------
    ann_vol = float(qs.stats.volatility(simple, periods=252))

    # --- Total return ---------------------------------------------------
    if not prices.empty and prices.iloc[0] != 0:
        total_return = float((prices.iloc[-1] / prices.iloc[0]) - 1.0)
    else:
        total_return = 0.0

    # --- Dividend contribution ------------------------------------------
    # Requires two price series (adj-close and raw close).  The current
    # fetcher only provides auto-adjusted prices, so we default to 0.0.
    div_contribution = 0.0

    return {
        "cagr": cagr,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown_pct": max_dd,
        "max_drawdown_recovery_months": recovery,
        "annualized_volatility": ann_vol,
        "total_return_pct": total_return,
        "dividend_contribution_pct": div_contribution,
    }

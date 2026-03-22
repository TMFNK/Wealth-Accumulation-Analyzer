"""Lump-sum simulation logic."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from wealth_analyzer.analysis.metrics import compute_metrics
from wealth_analyzer.config import AppConfig

logger = logging.getLogger(__name__)


def _align_series(
    stock_df: pd.DataFrame,
    etf_df: pd.DataFrame,
    user_start: pd.Timestamp,
    user_end: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp, pd.Timestamp]:
    """Align two price DataFrames to their shared trading window.

    Returns sliced copies of both DataFrames plus the actual
    ``analysis_start`` and ``analysis_end`` used.
    """
    start = max(stock_df.index[0], etf_df.index[0], user_start)
    end = min(stock_df.index[-1], etf_df.index[-1], user_end)
    stock_slice = stock_df.loc[start:end]
    etf_slice = etf_df.loc[start:end]
    return stock_slice, etf_slice, start, end


def run_lump_sum(
    prices: dict[str, pd.DataFrame],
    config: AppConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run lump-sum simulations for every stock x ETF pair.

    Parameters
    ----------
    prices:
        Mapping of ticker -> DataFrame with ``["Close", "Returns"]`` columns
        (as returned by ``fetch_prices``).
    config:
        Application configuration.

    Returns
    -------
    results_df
        One row per ``(stock, etf_benchmark)`` pair with all metrics.
    growth_df
        Time-indexed DataFrame, one column per unique ticker showing
        portfolio value over time starting from ``lump_sum_amount``.
    """
    amount = config.investment.lump_sum_amount
    rf = config.investment.risk_free_rate
    user_start = pd.Timestamp(config.general.start_date)
    user_end = pd.Timestamp(config.general.end_date)

    rows: list[dict] = []
    growth_frames: dict[str, pd.Series] = {}

    all_tickers = list(prices.keys())

    for ticker in all_tickers:
        if ticker not in prices:
            logger.warning("Ticker %s missing from prices — skipping", ticker)
            continue

        df = prices[ticker]
        # Build growth curve for this ticker (used for the growth_df output)
        first_close = df["Close"].iloc[0]
        growth = amount * (df["Close"] / first_close)
        growth_frames[ticker] = growth

    # For results_df, iterate stock × ETF pairs
    for stock in config.tickers.stocks:
        if stock not in prices:
            logger.warning("Stock %s missing from prices — skipping", stock)
            continue

        for etf in config.tickers.etfs:
            if etf not in prices:
                logger.warning("ETF %s missing from prices — skipping", etf)
                continue

            stock_slice, etf_slice, shared_start, shared_end = _align_series(
                prices[stock], prices[etf], user_start, user_end
            )

            if len(stock_slice) < 2 or len(etf_slice) < 2:
                logger.warning(
                    "Insufficient overlap for %s vs %s — skipping", stock, etf
                )
                continue

            # Compute metrics for stock
            stock_metrics = compute_metrics(
                stock_slice["Returns"], stock_slice["Close"], rf
            )

            # Compute metrics for ETF
            etf_metrics = compute_metrics(etf_slice["Returns"], etf_slice["Close"], rf)

            years = (shared_end - shared_start).days / 365.25

            row = {
                "ticker": stock,
                "benchmark": etf,
                "shared_start_date": shared_start.date()
                if hasattr(shared_start, "date")
                else shared_start,
                "end_date": shared_end.date()
                if hasattr(shared_end, "date")
                else shared_end,
                "years_analyzed": round(years, 2),
            }

            # Prefix stock metrics
            for k, v in stock_metrics.items():
                row[k] = v

            # Prefix ETF metrics with benchmark_
            for k, v in etf_metrics.items():
                row[f"benchmark_{k}"] = v

            # Outperformance
            stock_cagr = stock_metrics.get("cagr")
            etf_cagr = etf_metrics.get("cagr")
            if (
                isinstance(stock_cagr, (int, float))
                and isinstance(etf_cagr, (int, float))
                and np.isfinite(stock_cagr)
                and np.isfinite(etf_cagr)
            ):
                row["outperformance_cagr_pp"] = (stock_cagr - etf_cagr) * 100
            else:
                row["outperformance_cagr_pp"] = None

            stock_tr = stock_metrics.get("total_return_pct")
            etf_tr = etf_metrics.get("total_return_pct")
            if (
                isinstance(stock_tr, (int, float))
                and isinstance(etf_tr, (int, float))
                and np.isfinite(stock_tr)
                and np.isfinite(etf_tr)
            ):
                row["outperformance_total_return_pp"] = (stock_tr - etf_tr) * 100
            else:
                row["outperformance_total_return_pp"] = None

            rows.append(row)

            # Structured log output
            _log_performance_summary(
                stock,
                etf,
                shared_start,
                shared_end,
                years,
                stock_metrics,
                etf_metrics,
                amount,
            )

    results_df = pd.DataFrame(rows) if rows else pd.DataFrame()

    # Build growth_df from collected series
    if growth_frames:
        growth_df = pd.DataFrame(growth_frames)
        # Forward-fill single missing days for alignment
        growth_df = growth_df.ffill(limit=1)
    else:
        growth_df = pd.DataFrame()

    return results_df, growth_df


def _log_performance_summary(
    stock: str,
    etf: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    years: float,
    stock_m: dict,
    etf_m: dict,
    amount: float,
) -> None:
    """Emit a structured performance summary log block."""
    start_str = start.strftime("%Y-%m-%d") if hasattr(start, "strftime") else str(start)
    end_str = end.strftime("%Y-%m-%d") if hasattr(end, "strftime") else str(end)

    def _fmt_pct(v: object) -> str:
        if isinstance(v, (int, float)) and np.isfinite(v):
            return f"{v * 100:.1f}%"
        return "N/A"

    def _fmt_dd(v: object, recovery: object) -> str:
        if isinstance(v, (int, float)) and np.isfinite(v):
            s = f"{v * 100:.1f}%"
            if isinstance(recovery, (int, float)) and np.isfinite(recovery):
                s += f" (recovered {int(recovery)}mo)"
            else:
                s += " (not recovered)"
            return s
        return "N/A"

    cagr_diff = ""
    sc = stock_m.get("cagr")
    ec = etf_m.get("cagr")
    if (
        isinstance(sc, (int, float))
        and isinstance(ec, (int, float))
        and np.isfinite(sc)
        and np.isfinite(ec)
    ):
        diff_pp = (sc - ec) * 100
        cagr_diff = f"  ({diff_pp:+.1f}pp)"

    lines = [
        f"{'═' * 42}",
        f"  {stock}  vs  {etf}  |  {start_str} → {end_str}  ({years:.1f} yrs)",
        f"  Lump Sum: ${amount:,.0f}",
        f"{'─' * 42}",
        f"  CAGR:         {stock} {_fmt_pct(sc)}  |  {etf} {_fmt_pct(ec)}{cagr_diff}",
        f"  Total Return: {stock} {_fmt_pct(stock_m.get('total_return_pct'))}  |  {etf} {_fmt_pct(etf_m.get('total_return_pct'))}",
        f"  Sharpe:       {stock} {stock_m.get('sharpe', 0):.2f}   |  {etf} {etf_m.get('sharpe', 0):.2f}",
        f"  Sortino:      {stock} {stock_m.get('sortino', 0):.2f}   |  {etf} {etf_m.get('sortino', 0):.2f}",
        f"  Max DD:       {stock} {_fmt_dd(stock_m.get('max_drawdown_pct'), stock_m.get('max_drawdown_recovery_months'))}",
        f"               {etf} {_fmt_dd(etf_m.get('max_drawdown_pct'), etf_m.get('max_drawdown_recovery_months'))}",
        f"{'═' * 42}",
    ]
    logger.info("\n".join(lines))

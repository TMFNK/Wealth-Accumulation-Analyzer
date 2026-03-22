"""Dollar-cost averaging simulation logic."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from wealth_analyzer.analysis.metrics import compute_metrics, xirr
from wealth_analyzer.config import AppConfig

logger = logging.getLogger(__name__)


def _get_monthly_buy_dates(prices_index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Return the first trading day of each calendar month.

    Uses ``resample("MS")`` (Month Start) to group by calendar month,
    then takes the first available trading day in each group.
    """
    if len(prices_index) == 0:
        return pd.DatetimeIndex([])

    # Create a Series indexed by the price dates, group by month-start
    tmp = pd.Series(prices_index, index=prices_index)
    first_of_month = tmp.resample("MS").first()
    # The values are the first trading day in each month
    buy_dates = pd.DatetimeIndex(first_of_month.values)
    # Drop NaT if any
    buy_dates = buy_dates[buy_dates.notna()]
    return buy_dates


def run_dca(
    prices: dict[str, pd.DataFrame],
    config: AppConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run DCA simulations for every ticker in *prices*.

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
        One row per ticker with DCA-specific metrics.
    growth_df
        Time-indexed, one column per ticker = cumulative portfolio value.
    cost_basis_df
        Time-indexed, one column per ticker = cumulative cash invested.
    """
    monthly = config.investment.dca_monthly_amount
    rf = config.investment.risk_free_rate
    user_start = pd.Timestamp(config.general.start_date)
    user_end = pd.Timestamp(config.general.end_date)

    rows: list[dict] = []
    growth_frames: dict[str, pd.Series] = {}
    cost_frames: dict[str, pd.Series] = {}

    for ticker, df in prices.items():
        # Filter to user's requested date range
        mask = (df.index >= user_start) & (df.index <= user_end)
        ticker_df = df.loc[mask].copy()

        if len(ticker_df) < 2:
            logger.warning("Ticker %s has insufficient data — skipping", ticker)
            continue

        # Determine buy dates: first trading day of each calendar month
        buy_dates = _get_monthly_buy_dates(ticker_df.index)

        # Exclude the month containing the first data point if it falls
        # on the first trading day (per spec: start month excluded)
        first_ts = ticker_df.index[0]
        first_data_month_start = pd.Timestamp(first_ts.year, first_ts.month, 1)
        buy_dates = buy_dates[buy_dates >= first_data_month_start]

        # Also exclude if the buy date is exactly the first data point
        # (the spec says if analysis_start is the first trading day of a
        # month, that month is excluded)
        if len(buy_dates) > 0 and buy_dates[0] == ticker_df.index[0]:
            buy_dates = buy_dates[1:]

        # Only include buy dates within the data range
        buy_dates = buy_dates[buy_dates <= ticker_df.index[-1]]

        if len(buy_dates) == 0:
            logger.warning("No DCA buy dates for %s — skipping", ticker)
            continue

        # Build cumulative shares series (vectorized via reindex + ffill)
        shares_per_day = pd.Series(0.0, index=ticker_df.index, dtype=float)
        cost_per_day = pd.Series(0.0, index=ticker_df.index, dtype=float)

        cumulative_shares = 0.0
        cumulative_cost = 0.0
        purchase_records: list[tuple] = []
        cashflows: list[tuple] = []

        for buy_date in buy_dates:
            if buy_date not in ticker_df.index:
                # Shouldn't happen since buy_dates comes from the index
                continue
            price_on_date = float(ticker_df.loc[buy_date, "Close"])
            if price_on_date <= 0:
                logger.warning(
                    "Zero/negative price for %s on %s — skipping buy", ticker, buy_date
                )
                continue

            new_shares = monthly / price_on_date
            cumulative_shares += new_shares
            cumulative_cost += monthly

            shares_per_day.loc[buy_date:] = cumulative_shares
            cost_per_day.loc[buy_date:] = cumulative_cost

            purchase_records.append(
                (buy_date.date(), new_shares, price_on_date, monthly)
            )
            cashflows.append((buy_date.date(), -monthly))

        # Portfolio value = cumulative_shares × price each day
        portfolio_value = shares_per_day * ticker_df["Close"]

        # Terminal cashflow for XIRR
        final_value = float(portfolio_value.iloc[-1])
        final_date = ticker_df.index[-1].date()
        cashflows.append((final_date, final_value))

        # Compute XIRR
        xirr_val = None
        try:
            xirr_val = xirr(cashflows)
        except (ValueError, RuntimeError):
            logger.warning("XIRR did not converge for %s", ticker)

        # Compute metrics on the asset's return series (not portfolio)
        metrics = compute_metrics(ticker_df["Returns"], ticker_df["Close"], rf)

        # Best/worst entry month: return on each individual monthly purchase
        best_month = None
        best_return = None
        worst_month = None
        worst_return = None

        if purchase_records and len(purchase_records) > 0:
            returns_per_month: list[tuple] = []
            last_close = float(ticker_df["Close"].iloc[-1])
            for buy_d, shares_bought, buy_price, _ in purchase_records:
                if buy_price > 0:
                    # The return if this single purchase were held to the end
                    single_return = (last_close / buy_price) - 1.0
                    returns_per_month.append((buy_d, single_return))

            if returns_per_month:
                best_entry = max(returns_per_month, key=lambda x: x[1])
                worst_entry = min(returns_per_month, key=lambda x: x[1])
                best_month = str(best_entry[0])
                best_return = best_entry[1]
                worst_month = str(worst_entry[0])
                worst_return = worst_entry[1]

        avg_cost = cumulative_cost / cumulative_shares if cumulative_shares > 0 else 0.0

        row = {
            "ticker": ticker,
            "total_contributions": cumulative_cost,
            "final_value": final_value,
            "xirr_pct": xirr_val,
            "best_entry_month": best_month,
            "best_entry_return_pct": best_return,
            "worst_entry_month": worst_month,
            "worst_entry_return_pct": worst_return,
            "avg_cost_per_share": avg_cost,
            "current_price": float(ticker_df["Close"].iloc[-1]),
            "multiple_on_invested": final_value / cumulative_cost
            if cumulative_cost > 0
            else None,
        }

        # Add standard metrics
        for k, v in metrics.items():
            row[k] = v

        rows.append(row)
        growth_frames[ticker] = portfolio_value
        cost_frames[ticker] = cost_per_day

        # Log DCA summary
        _log_dca_summary(
            ticker, cumulative_cost, final_value, xirr_val, len(buy_dates), monthly
        )

    results_df = pd.DataFrame(rows) if rows else pd.DataFrame()

    # Build aligned DataFrames
    if growth_frames:
        growth_df = pd.DataFrame(growth_frames).ffill(limit=1)
        cost_basis_df = pd.DataFrame(cost_frames).ffill(limit=1)
    else:
        growth_df = pd.DataFrame()
        cost_basis_df = pd.DataFrame()

    return results_df, growth_df, cost_basis_df


def _log_dca_summary(
    ticker: str,
    total_invested: float,
    final_value: float,
    xirr_val: float | None,
    num_months: int,
    monthly: float,
) -> None:
    """Emit a structured DCA summary log block."""
    xirr_str = (
        f"{xirr_val * 100:.1f}%"
        if xirr_val is not None and np.isfinite(xirr_val)
        else "N/A"
    )
    gain = final_value - total_invested
    gain_pct = (gain / total_invested * 100) if total_invested > 0 else 0.0

    lines = [
        f"{'═' * 42}",
        f"  [DCA] {ticker}",
        f"  {num_months} months × ${monthly:,.0f}/month",
        f"{'─' * 42}",
        f"  Total Invested:  ${total_invested:,.2f}",
        f"  Final Value:     ${final_value:,.2f}",
        f"  Net Gain/Loss:   ${gain:,.2f}  ({gain_pct:+.1f}%)",
        f"  XIRR:            {xirr_str}",
        f"{'═' * 42}",
    ]
    logger.info("\n".join(lines))

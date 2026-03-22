"""Tests for the lump-sum simulation."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from wealth_analyzer.analysis.lump_sum import run_lump_sum
from wealth_analyzer.config import (
    AppConfig,
    GeneralConfig,
    InvestmentConfig,
    TickersConfig,
    OutputConfig,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_prices(
    start: date,
    end: date,
    *,
    base_price: float = 100.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Build a synthetic price DataFrame matching fetcher output."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, end)
    n = len(dates)
    prices = base_price + rng.standard_normal(n).cumsum() * 2
    prices = np.abs(prices) + 50  # keep positive
    close = pd.Series(prices, index=dates, name="Close")
    log_ret = np.log(close / close.shift(1)).dropna()
    close = close.loc[log_ret.index]
    return pd.DataFrame({"Close": close, "Returns": log_ret})


def _make_config(
    *,
    start: date = date(2019, 1, 2),
    end: date = date(2023, 12, 29),
    lump_sum: float = 10_000.0,
    dca_monthly: float = 500.0,
    risk_free: float = 0.045,
    stocks: list[str] | None = None,
    etfs: list[str] | None = None,
) -> AppConfig:
    return AppConfig(
        general=GeneralConfig(start_date=start, end_date=end, cache_ttl_days=1),
        investment=InvestmentConfig(
            lump_sum_amount=lump_sum,
            dca_monthly_amount=dca_monthly,
            risk_free_rate=risk_free,
        ),
        tickers=TickersConfig(
            stocks=stocks or ["AAPL"],
            etfs=etfs or ["SPY"],
        ),
        output=OutputConfig(),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRunLumpSum:
    def test_results_df_shape(self) -> None:
        """One row per (stock, etf) pair."""
        prices = {
            "AAPL": _make_prices(date(2019, 1, 2), date(2023, 12, 29), seed=1),
            "SPY": _make_prices(date(2019, 1, 2), date(2023, 12, 29), seed=2),
        }
        cfg = _make_config()
        results_df, growth_df = run_lump_sum(prices, cfg)
        assert len(results_df) == 1  # 1 stock × 1 ETF
        assert "ticker" in results_df.columns
        assert "benchmark" in results_df.columns

    def test_growth_df_columns(self) -> None:
        """Growth df has one column per unique ticker."""
        prices = {
            "AAPL": _make_prices(date(2019, 1, 2), date(2023, 12, 29), seed=1),
            "SPY": _make_prices(date(2019, 1, 2), date(2023, 12, 29), seed=2),
        }
        cfg = _make_config()
        _, growth_df = run_lump_sum(prices, cfg)
        assert "AAPL" in growth_df.columns
        assert "SPY" in growth_df.columns

    def test_growth_starts_at_lump_sum(self) -> None:
        """First growth value should equal lump_sum_amount."""
        prices = {
            "AAPL": _make_prices(date(2019, 1, 2), date(2023, 12, 29), seed=1),
            "SPY": _make_prices(date(2019, 1, 2), date(2023, 12, 29), seed=2),
        }
        cfg = _make_config(lump_sum=10_000.0)
        _, growth_df = run_lump_sum(prices, cfg)
        assert abs(growth_df["AAPL"].iloc[0] - 10_000.0) < 1e-6

    def test_multiple_stocks_and_etfs(self) -> None:
        """With 2 stocks and 2 ETFs, results_df has 4 rows."""
        prices = {
            "AAPL": _make_prices(date(2019, 1, 2), date(2023, 12, 29), seed=1),
            "MSFT": _make_prices(date(2019, 1, 2), date(2023, 12, 29), seed=3),
            "SPY": _make_prices(date(2019, 1, 2), date(2023, 12, 29), seed=2),
            "QQQM": _make_prices(date(2019, 1, 2), date(2023, 12, 29), seed=4),
        }
        cfg = _make_config(stocks=["AAPL", "MSFT"], etfs=["SPY", "QQQM"])
        results_df, growth_df = run_lump_sum(prices, cfg)
        assert len(results_df) == 4
        assert set(growth_df.columns) == {"AAPL", "MSFT", "SPY", "QQQM"}

    def test_missing_ticker_skipped(self) -> None:
        """If a stock is missing from prices, skip that pair."""
        prices = {
            "SPY": _make_prices(date(2019, 1, 2), date(2023, 12, 29), seed=2),
        }
        cfg = _make_config(stocks=["AAPL"], etfs=["SPY"])
        results_df, _ = run_lump_sum(prices, cfg)
        # AAPL is missing → no rows produced
        assert len(results_df) == 0

    def test_metrics_present(self) -> None:
        """Results include cagr, sharpe, max_drawdown_pct."""
        prices = {
            "AAPL": _make_prices(date(2019, 1, 2), date(2023, 12, 29), seed=1),
            "SPY": _make_prices(date(2019, 1, 2), date(2023, 12, 29), seed=2),
        }
        cfg = _make_config()
        results_df, _ = run_lump_sum(prices, cfg)
        row = results_df.iloc[0]
        assert "cagr" in results_df.columns
        assert "sharpe" in results_df.columns
        assert "max_drawdown_pct" in results_df.columns
        assert isinstance(row["cagr"], float)

    def test_outperformance_columns(self) -> None:
        """Results include outperformance in percentage points."""
        prices = {
            "AAPL": _make_prices(date(2019, 1, 2), date(2023, 12, 29), seed=1),
            "SPY": _make_prices(date(2019, 1, 2), date(2023, 12, 29), seed=2),
        }
        cfg = _make_config()
        results_df, _ = run_lump_sum(prices, cfg)
        assert "outperformance_cagr_pp" in results_df.columns

    def test_aligned_start_date(self) -> None:
        """Shared start date in results is max of both tickers' first dates."""
        # AAPL starts later
        aapl = _make_prices(date(2020, 1, 2), date(2023, 12, 29), seed=1)
        spy = _make_prices(date(2019, 1, 2), date(2023, 12, 29), seed=2)
        prices = {"AAPL": aapl, "SPY": spy}
        cfg = _make_config(start=date(2019, 1, 2))
        results_df, _ = run_lump_sum(prices, cfg)
        # The shared_start_date in results should be AAPL's first date
        row = results_df.iloc[0]
        assert row["shared_start_date"] >= date(2020, 1, 2)

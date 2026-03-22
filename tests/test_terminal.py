"""Tests for terminal report rendering."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from wealth_analyzer.config import (
    AppConfig,
    GeneralConfig,
    InvestmentConfig,
    OutputConfig,
    TickersConfig,
)
from wealth_analyzer.reports.terminal import print_lump_sum_summary, print_dca_summary


def _make_config() -> AppConfig:
    return AppConfig(
        general=GeneralConfig(
            start_date=date(2019, 1, 2), end_date=date(2023, 12, 29), cache_ttl_days=1
        ),
        investment=InvestmentConfig(
            lump_sum_amount=10_000, dca_monthly_amount=500, risk_free_rate=0.045
        ),
        tickers=TickersConfig(stocks=["AAPL"], etfs=["SPY"]),
        output=OutputConfig(),
    )


def _make_lump_results() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "benchmark": "SPY",
                "shared_start_date": date(2019, 1, 2),
                "end_date": date(2023, 12, 29),
                "years_analyzed": 5.0,
                "cagr": 0.25,
                "total_return_pct": 2.05,
                "sharpe": 1.1,
                "sortino": 1.5,
                "max_drawdown_pct": -0.30,
                "outperformance_cagr_pp": 12.5,
            }
        ]
    )


def _make_dca_results() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "total_contributions": 30_000,
                "final_value": 45_000,
                "xirr_pct": 0.12,
                "cagr": 0.20,
                "sharpe": 1.0,
                "sortino": 1.3,
                "max_drawdown_pct": -0.25,
                "best_entry_month": "2020-03-01",
                "worst_entry_month": "2021-11-01",
            }
        ]
    )


class TestPrintLumpSum:
    def test_renders_normal(self) -> None:
        """Should not raise for normal results_df."""
        print_lump_sum_summary(_make_lump_results(), _make_config())

    def test_renders_empty(self) -> None:
        """Should not raise for empty results_df."""
        print_lump_sum_summary(pd.DataFrame(), _make_config())

    def test_nan_values_no_crash(self) -> None:
        df = _make_lump_results()
        df.loc[0, "cagr"] = np.nan
        print_lump_sum_summary(df, _make_config())

    def test_none_values_no_crash(self) -> None:
        df = _make_lump_results()
        df.loc[0, "outperformance_cagr_pp"] = None
        print_lump_sum_summary(df, _make_config())

    def test_positive_outperformance(self) -> None:
        df = _make_lump_results()
        df.loc[0, "outperformance_cagr_pp"] = 5.0
        print_lump_sum_summary(df, _make_config())

    def test_negative_outperformance(self) -> None:
        df = _make_lump_results()
        df.loc[0, "outperformance_cagr_pp"] = -5.0
        print_lump_sum_summary(df, _make_config())

    def test_sort_by_outperformance(self) -> None:
        df = pd.DataFrame(
            [
                {
                    "ticker": "AAPL",
                    "benchmark": "SPY",
                    "outperformance_cagr_pp": 5.0,
                    "cagr": 0.2,
                    "total_return_pct": 1.0,
                    "sharpe": 1.0,
                    "max_drawdown_pct": -0.2,
                },
                {
                    "ticker": "MSFT",
                    "benchmark": "SPY",
                    "outperformance_cagr_pp": 15.0,
                    "cagr": 0.3,
                    "total_return_pct": 2.0,
                    "sharpe": 1.2,
                    "max_drawdown_pct": -0.15,
                },
            ]
        )
        # Should not raise
        print_lump_sum_summary(df, _make_config())


class TestPrintDcaSummary:
    def test_renders_normal(self) -> None:
        print_dca_summary(_make_dca_results(), _make_config())

    def test_renders_empty(self) -> None:
        print_dca_summary(pd.DataFrame(), _make_config())

    def test_nan_xirr_no_crash(self) -> None:
        df = _make_dca_results()
        df.loc[0, "xirr_pct"] = np.nan
        print_dca_summary(df, _make_config())

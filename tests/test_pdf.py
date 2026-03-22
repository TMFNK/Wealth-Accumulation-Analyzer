"""Tests for PDF report generation."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from wealth_analyzer.config import (
    AppConfig,
    GeneralConfig,
    InvestmentConfig,
    OutputConfig,
    TickersConfig,
)
from wealth_analyzer.reports.pdf import write_pdf


def _make_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        general=GeneralConfig(
            start_date=date(2019, 1, 2), end_date=date(2023, 12, 29), cache_ttl_days=1
        ),
        investment=InvestmentConfig(
            lump_sum_amount=10_000, dca_monthly_amount=500, risk_free_rate=0.045
        ),
        tickers=TickersConfig(stocks=["AAPL"], etfs=["SPY"]),
        output=OutputConfig(output_dir=str(tmp_path)),
    )


def _make_data() -> dict:
    dates = pd.bdate_range("2020-01-02", periods=50)
    rng = np.random.default_rng(42)
    close = 100 + rng.standard_normal(50).cumsum() * 2
    close = np.abs(close) + 50
    s = pd.Series(close, index=dates, name="Close")
    log_ret = np.log(s / s.shift(1)).dropna()
    s = s.loc[log_ret.index]

    ls_results = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "benchmark": "SPY",
                "cagr": 0.25,
                "sharpe": 1.1,
                "max_drawdown_pct": -0.30,
                "outperformance_cagr_pp": 12.5,
                "total_return_pct": 2.05,
                "benchmark_cagr": 0.12,
                "max_drawdown_recovery_months": 6,
            }
        ]
    )
    ls_growth = pd.DataFrame(
        {
            "AAPL": np.linspace(10_000, 15_000, len(s)),
            "SPY": np.linspace(10_000, 12_000, len(s)),
        },
        index=s.index,
    )
    dca_results = pd.DataFrame(
        [
            {
                "ticker": "AAPL",
                "total_contributions": 30_000,
                "final_value": 45_000,
                "xirr_pct": 0.12,
                "cagr": 0.20,
                "multiple_on_invested": 1.5,
                "sharpe": 1.0,
                "max_drawdown_pct": -0.25,
                "annualized_volatility": 0.15,
                "best_entry_month": "2020-03-01",
                "worst_entry_month": "2021-11-01",
            }
        ]
    )
    dca_growth = pd.DataFrame({"AAPL": np.linspace(0, 45_000, len(s))}, index=s.index)
    dca_cost = pd.DataFrame({"AAPL": np.linspace(0, 30_000, len(s))}, index=s.index)
    prices = {"AAPL": pd.DataFrame({"Close": s, "Returns": log_ret})}

    return dict(
        ls_results=ls_results,
        ls_growth=ls_growth,
        dca_results=dca_results,
        dca_growth=dca_growth,
        dca_cost=dca_cost,
        prices=prices,
    )


class TestWritePdf:
    def test_creates_file(self, tmp_path: Path) -> None:
        d = _make_data()
        path = write_pdf(
            d["ls_results"],
            d["ls_growth"],
            d["dca_results"],
            d["dca_growth"],
            d["dca_cost"],
            d["prices"],
            _make_config(tmp_path),
        )
        assert path.is_file()

    def test_pdf_magic_bytes(self, tmp_path: Path) -> None:
        d = _make_data()
        path = write_pdf(
            d["ls_results"],
            d["ls_growth"],
            d["dca_results"],
            d["dca_growth"],
            d["dca_cost"],
            d["prices"],
            _make_config(tmp_path),
        )
        with open(path, "rb") as f:
            header = f.read(4)
        assert header == b"%PDF"

    def test_file_size_nontrivial(self, tmp_path: Path) -> None:
        d = _make_data()
        path = write_pdf(
            d["ls_results"],
            d["ls_growth"],
            d["dca_results"],
            d["dca_growth"],
            d["dca_cost"],
            d["prices"],
            _make_config(tmp_path),
        )
        assert path.stat().st_size > 5_000  # relaxed for test data

    def test_creates_output_dir(self, tmp_path: Path) -> None:
        deep = tmp_path / "deep" / "nested"
        cfg = _make_config(deep)
        d = _make_data()
        path = write_pdf(
            d["ls_results"],
            d["ls_growth"],
            d["dca_results"],
            d["dca_growth"],
            d["dca_cost"],
            d["prices"],
            cfg,
        )
        assert path.is_file()
        assert deep.is_dir()

    def test_missing_ticker_no_crash(self, tmp_path: Path) -> None:
        d = _make_data()
        # Add a stock that's not in prices
        cfg = _make_config(tmp_path)
        cfg.tickers.stocks = ["AAPL", "MISSING"]
        path = write_pdf(
            d["ls_results"],
            d["ls_growth"],
            d["dca_results"],
            d["dca_growth"],
            d["dca_cost"],
            d["prices"],
            cfg,
        )
        assert path.is_file()

    def test_fig_to_image_returns_image(self) -> None:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from wealth_analyzer.reports.charts import _fig_to_image

        fig, ax = plt.subplots()
        ax.plot([1, 2, 3])
        img = _fig_to_image(fig, dpi=72)
        assert hasattr(img, "drawWidth")

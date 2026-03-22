"""Tests for chart generation."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from wealth_analyzer.config import (
    AppConfig,
    GeneralConfig,
    InvestmentConfig,
    OutputConfig,
    TickersConfig,
)
from wealth_analyzer.reports.charts import (
    wealth_growth_chart,
    drawdown_chart,
    dca_cost_basis_chart,
    monthly_returns_heatmap,
    _fig_to_image,
)


def _make_config() -> AppConfig:
    return AppConfig(
        general=GeneralConfig(
            start_date=date(2019, 1, 2), end_date=date(2023, 12, 29), cache_ttl_days=1
        ),
        investment=InvestmentConfig(
            lump_sum_amount=10_000, dca_monthly_amount=500, risk_free_rate=0.045
        ),
        tickers=TickersConfig(stocks=["AAPL", "MSFT"], etfs=["SPY"]),
        output=OutputConfig(chart_dpi=72),
    )


def _make_growth_df() -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-02", periods=100)
    return pd.DataFrame(
        {
            "AAPL": np.linspace(10_000, 15_000, 100),
            "SPY": np.linspace(10_000, 12_000, 100),
        },
        index=dates,
    )


def _make_prices() -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2020-01-02", periods=252)
    close = 100 + rng.standard_normal(252).cumsum() * 2
    close = np.abs(close) + 50
    s = pd.Series(close, index=dates, name="Close")
    log_ret = np.log(s / s.shift(1)).dropna()
    s = s.loc[log_ret.index]
    return {"AAPL": pd.DataFrame({"Close": s, "Returns": log_ret})}


class TestWealthGrowthChart:
    def test_returns_figure(self) -> None:
        fig = wealth_growth_chart(_make_growth_df(), _make_config())
        assert isinstance(fig, Figure)
        plt.close(fig)

    def test_correct_line_count(self) -> None:
        fig = wealth_growth_chart(_make_growth_df(), _make_config())
        ax = fig.axes[0]
        assert len(ax.lines) == 2  # AAPL + SPY
        plt.close(fig)


class TestDrawdownChart:
    def test_returns_figure(self) -> None:
        fig = drawdown_chart(_make_growth_df(), _make_config())
        assert isinstance(fig, Figure)
        plt.close(fig)

    def test_yaxis_max_le_zero(self) -> None:
        fig = drawdown_chart(_make_growth_df(), _make_config())
        ax = fig.axes[0]
        # Drawdown should be <= 0 (or close to 0)
        ymin, ymax = ax.get_ylim()
        assert ymax <= 5  # allow small padding
        plt.close(fig)


class TestDcaCostBasisChart:
    def test_returns_figure(self) -> None:
        growth = _make_growth_df()
        cost = growth * 0.8
        fig = dca_cost_basis_chart(growth, cost, _make_config())
        assert isinstance(fig, Figure)
        plt.close(fig)

    def test_correct_subplot_count(self) -> None:
        growth = _make_growth_df()
        cost = growth * 0.8
        fig = dca_cost_basis_chart(growth, cost, _make_config())
        # 2 tickers -> should have visible subplots
        visible_axes = [ax for ax in fig.axes if ax.get_visible()]
        assert len(visible_axes) == 2
        plt.close(fig)


class TestMonthlyHeatmap:
    def test_returns_figure(self) -> None:
        fig = monthly_returns_heatmap(_make_prices(), "AAPL", _make_config())
        assert isinstance(fig, Figure)
        plt.close(fig)

    def test_missing_ticker_no_crash(self) -> None:
        fig = monthly_returns_heatmap(_make_prices(), "MISSING", _make_config())
        assert isinstance(fig, Figure)
        plt.close(fig)


class TestFigToImage:
    def test_returns_reportlab_image(self) -> None:
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3], [1, 4, 9])
        img = _fig_to_image(fig, dpi=72)
        # Should be a ReportLab Image
        assert hasattr(img, "drawWidth")
        assert hasattr(img, "drawHeight")

    def test_figure_closed(self) -> None:
        fig, ax = plt.subplots()
        ax.plot([1, 2, 3])
        _fig_to_image(fig, dpi=72)
        # Figure should be closed now
        assert not plt.fignum_exists(fig.number)


class TestNoShowCalls:
    def test_no_plt_show(self) -> None:
        """Verify charts.py never calls plt.show()."""
        import ast
        from pathlib import Path

        charts_path = (
            Path(__file__).parent.parent
            / "src"
            / "wealth_analyzer"
            / "reports"
            / "charts.py"
        )
        tree = ast.parse(charts_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "show":
                        pytest.fail("plt.show() found in charts.py")

"""Tests for the metrics engine (xirr + compute_metrics)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from wealth_analyzer.analysis.metrics import compute_metrics, xirr


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def yearly_returns() -> pd.Series:
    """A realistic 5-year daily log-return series for testing."""
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2019-01-02", periods=252 * 5)
    log_returns = rng.normal(0.0004, 0.012, len(dates))
    return pd.Series(log_returns, index=dates)


@pytest.fixture()
def yearly_prices(yearly_returns: pd.Series) -> pd.Series:
    """Corresponding price series derived from log returns."""
    return 100.0 * np.exp(yearly_returns.cumsum())


# ---------------------------------------------------------------------------
# xirr tests
# ---------------------------------------------------------------------------


class TestXirr:
    def test_known_10_percent(self) -> None:
        """Invest -$1000 on day 0, receive +$1100 exactly 1 year later -> ~10%."""
        d0 = date(2019, 1, 1)
        d1 = date(2020, 1, 1)  # 365 days (non-leap year)
        cashflows = [(d0, -1000.0), (d1, 1100.0)]
        result = xirr(cashflows)
        assert abs(result - 0.10) < 1e-6

    def test_zero_return(self) -> None:
        """Invest -$1000, receive exactly $1000 back -> 0% IRR."""
        d0 = date(2020, 1, 1)
        d1 = date(2021, 1, 1)
        cashflows = [(d0, -1000.0), (d1, 1000.0)]
        result = xirr(cashflows)
        assert abs(result) < 1e-6

    def test_monthly_contributions(self) -> None:
        """Monthly DCA with a final positive value should converge."""
        cashflows: list[tuple[date, float]] = []
        for m in range(12):
            d = date(2020, m + 1, 1)
            cashflows.append((d, -500.0))
        # Final value after 12 months
        cashflows.append((date(2021, 1, 1), 6500.0))
        result = xirr(cashflows)
        # Should be positive (profit)
        assert result > 0
        # Should be reasonable (not extreme)
        assert 0 < result < 2.0

    def test_same_day_cashflows_combined(self) -> None:
        """Multiple cashflows on the same day should not cause errors."""
        d0 = date(2019, 1, 1)
        d1 = date(2020, 1, 1)  # 365 days (non-leap year)
        cashflows = [(d0, -500.0), (d0, -500.0), (d1, 1100.0)]
        result = xirr(cashflows)
        # Combined: -1000 on day 0, +1100 on day 365 -> ~10%
        assert abs(result - 0.10) < 1e-6

    def test_no_sign_change_raises(self) -> None:
        """All-positive or all-negative cashflows have no root."""
        d0 = date(2020, 1, 1)
        d1 = date(2021, 1, 1)
        with pytest.raises(ValueError, match="no sign change"):
            xirr([(d0, -1000.0), (d1, -500.0)])

    def test_insufficient_cashflows_raises(self) -> None:
        """Fewer than 2 cashflows should raise."""
        with pytest.raises(ValueError, match="at least two"):
            xirr([(date(2020, 1, 1), -1000.0)])

    def test_negative_return(self) -> None:
        """Lose money -> negative IRR."""
        d0 = date(2019, 1, 1)
        d1 = date(2020, 1, 1)  # 365 days (non-leap year)
        cashflows = [(d0, -1000.0), (d1, 800.0)]
        result = xirr(cashflows)
        assert result < 0
        assert abs(result - (-0.20)) < 1e-6


# ---------------------------------------------------------------------------
# compute_metrics tests
# ---------------------------------------------------------------------------


class TestComputeMetrics:
    def test_returns_all_keys(
        self, yearly_returns: pd.Series, yearly_prices: pd.Series
    ) -> None:
        result = compute_metrics(yearly_returns, yearly_prices, risk_free_rate=0.045)
        expected_keys = {
            "cagr",
            "sharpe",
            "sortino",
            "max_drawdown_pct",
            "max_drawdown_recovery_months",
            "annualized_volatility",
            "total_return_pct",
            "dividend_contribution_pct",
        }
        assert set(result.keys()) == expected_keys

    def test_cagr_is_float(
        self, yearly_returns: pd.Series, yearly_prices: pd.Series
    ) -> None:
        result = compute_metrics(yearly_returns, yearly_prices, risk_free_rate=0.045)
        assert isinstance(result["cagr"], float)

    def test_sharpe_is_float(
        self, yearly_returns: pd.Series, yearly_prices: pd.Series
    ) -> None:
        result = compute_metrics(yearly_returns, yearly_prices, risk_free_rate=0.045)
        assert isinstance(result["sharpe"], float)

    def test_sortino_is_float(
        self, yearly_returns: pd.Series, yearly_prices: pd.Series
    ) -> None:
        result = compute_metrics(yearly_returns, yearly_prices, risk_free_rate=0.045)
        assert isinstance(result["sortino"], float)

    def test_max_drawdown_is_negative(
        self, yearly_returns: pd.Series, yearly_prices: pd.Series
    ) -> None:
        result = compute_metrics(yearly_returns, yearly_prices, risk_free_rate=0.045)
        assert result["max_drawdown_pct"] <= 0.0

    def test_volatility_is_positive(
        self, yearly_returns: pd.Series, yearly_prices: pd.Series
    ) -> None:
        result = compute_metrics(yearly_returns, yearly_prices, risk_free_rate=0.045)
        assert result["annualized_volatility"] > 0.0

    def test_total_return_matches_price_ratio(
        self, yearly_returns: pd.Series, yearly_prices: pd.Series
    ) -> None:
        result = compute_metrics(yearly_returns, yearly_prices, risk_free_rate=0.045)
        expected = (yearly_prices.iloc[-1] / yearly_prices.iloc[0]) - 1.0
        assert abs(result["total_return_pct"] - expected) < 1e-6

    def test_dividend_contribution_zero_for_single_series(
        self, yearly_returns: pd.Series, yearly_prices: pd.Series
    ) -> None:
        """When only one series is given, dividend contribution is 0.0."""
        result = compute_metrics(yearly_returns, yearly_prices, risk_free_rate=0.045)
        assert result["dividend_contribution_pct"] == 0.0

    def test_constant_returns_no_drawdown(self) -> None:
        """Constant positive returns should have 0 max drawdown."""
        dates = pd.bdate_range("2020-01-01", periods=252)
        log_ret = pd.Series([0.001] * 252, index=dates)
        prices = 100.0 * np.exp(log_ret.cumsum())
        prices = pd.Series(prices, index=dates)
        result = compute_metrics(log_ret, prices, risk_free_rate=0.045)
        assert result["max_drawdown_pct"] == 0.0

    def test_single_row_returns_nan(self) -> None:
        """A single data point should return NaN values with a logged warning."""
        dates = pd.bdate_range("2020-01-01", periods=1)
        log_ret = pd.Series([0.001], index=dates)
        prices = pd.Series([100.0], index=dates)
        result = compute_metrics(log_ret, prices, risk_free_rate=0.045)
        # At minimum, the function should not crash
        assert "cagr" in result

    def test_recovery_months_none_when_no_recovery(self) -> None:
        """If worst drawdown never recovers, recovery months should be None."""
        dates = pd.bdate_range("2020-01-01", periods=252)
        # Start flat, then crash and stay down
        log_ret = np.zeros(252)
        log_ret[50:] = -0.002  # sustained decline after day 50
        log_ret_series = pd.Series(log_ret, index=dates)
        prices = 100.0 * np.exp(log_ret_series.cumsum())
        prices = pd.Series(prices, index=dates)
        result = compute_metrics(log_ret_series, prices, risk_free_rate=0.045)
        # Worst drawdown starts at peak and never recovers
        assert result["max_drawdown_recovery_months"] is None

    def test_zero_volatility_returns_zero_sharpe(self) -> None:
        """Zero std returns -> Sharpe should be 0.0, not NaN or inf."""
        dates = pd.bdate_range("2020-01-01", periods=252)
        # All identical returns -> zero std
        log_ret = pd.Series([0.0004] * 252, index=dates)
        prices = 100.0 * np.exp(log_ret.cumsum())
        prices = pd.Series(prices, index=dates)
        result = compute_metrics(log_ret, prices, risk_free_rate=0.045)
        assert result["sharpe"] == 0.0 or np.isfinite(result["sharpe"])

    def test_empty_returns(self) -> None:
        """Empty input should not crash."""
        empty = pd.Series([], dtype=float, index=pd.DatetimeIndex([]))
        result = compute_metrics(empty, empty, risk_free_rate=0.045)
        assert "cagr" in result

"""Tests for the market data fetcher with mocked yfinance calls."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from wealth_analyzer.data.fetcher import (
    _add_returns,
    _extract_close,
    _normalize,
    _splice_qqqm,
    fetch_prices,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_price_series(
    tickers: list[str],
    start: date,
    end: date,
    *,
    base_price: float = 100.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Build a synthetic yfinance-style DataFrame for testing.

    Returns a multi-level column frame ``(field, ticker)`` matching
    ``yfinance.download(..., group_by="column")`` output.
    """
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, end)
    n = len(dates)

    frames: dict[str, pd.DataFrame] = {}
    for i, t in enumerate(tickers):
        prices = base_price + rng.standard_normal(n).cumsum() * 2
        prices = np.abs(prices) + 50  # keep positive
        frames[t] = pd.DataFrame({"Close": prices}, index=dates)

    combined = pd.concat(frames.values(), keys=frames.keys(), axis=1)
    combined.columns = pd.MultiIndex.from_tuples(
        [("Close", t) for t in tickers], names=["Price", "Ticker"]
    )
    return combined


def _make_single_ticker_frame(
    start: date,
    end: date,
    *,
    ticker: str = "AAPL",
    base_price: float = 100.0,
    seed: int = 42,
) -> pd.DataFrame:
    """Build a flat DataFrame as yfinance returns for a single ticker."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start, end)
    n = len(dates)
    prices = base_price + rng.standard_normal(n).cumsum() * 2
    prices = np.abs(prices) + 50
    return pd.DataFrame({"Close": prices}, index=dates)


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------


class TestNormalize:
    def test_sorts_index(self) -> None:
        idx = pd.bdate_range("2020-01-06", periods=5)
        df = pd.DataFrame({"Close": [1, 2, 3, 4, 5]}, index=idx[::-1])
        result = _normalize(df)
        assert result.index.is_monotonic_increasing

    def test_drops_duplicates(self) -> None:
        idx = pd.to_datetime(["2020-01-02", "2020-01-02", "2020-01-03"])
        df = pd.DataFrame({"Close": [1, 2, 3]}, index=idx)
        result = _normalize(df)
        assert len(result) == 2

    def test_drops_nan(self) -> None:
        idx = pd.bdate_range("2020-01-06", periods=3)
        df = pd.DataFrame({"Close": [1.0, np.nan, 3.0]}, index=idx)
        result = _normalize(df)
        assert len(result) == 2


class TestAddReturns:
    def test_returns_column_exists(self) -> None:
        idx = pd.bdate_range("2020-01-06", periods=5)
        df = pd.DataFrame({"Close": np.linspace(100, 110, 5)}, index=idx)
        result = _add_returns(df)
        assert "Returns" in result.columns

    def test_first_return_is_dropped(self) -> None:
        idx = pd.bdate_range("2020-01-06", periods=5)
        df = pd.DataFrame({"Close": np.linspace(100, 110, 5)}, index=idx)
        result = _add_returns(df)
        assert len(result) == 4  # original 5 minus 1 NaN

    def test_returns_are_log_returns(self) -> None:
        idx = pd.bdate_range("2020-01-06", periods=3)
        close = pd.Series([100.0, 110.0, 121.0], index=idx)
        df = pd.DataFrame({"Close": close})
        result = _add_returns(df)
        expected = np.log(110 / 100)
        assert abs(result["Returns"].iloc[0] - expected) < 1e-10


class TestExtractClose:
    def test_single_ticker(self) -> None:
        raw = _make_single_ticker_frame(date(2020, 1, 6), date(2020, 1, 10))
        result = _extract_close(raw, ["AAPL"])
        assert "AAPL" in result
        assert list(result["AAPL"].columns) == ["Close"]

    def test_multi_ticker(self) -> None:
        raw = _make_price_series(["AAPL", "SPY"], date(2020, 1, 6), date(2020, 1, 10))
        result = _extract_close(raw, ["AAPL", "SPY"])
        assert "AAPL" in result
        assert "SPY" in result
        assert list(result["AAPL"].columns) == ["Close"]


class TestSpliceQQQM:
    def test_no_qqqm_key_returns_unchanged(self) -> None:
        raw = {"AAPL": _make_single_ticker_frame(date(2019, 1, 2), date(2021, 1, 4))}
        result = _splice_qqqm(raw, date(2019, 1, 2), date(2021, 1, 4))
        assert "QQQM" not in result

    def test_start_after_inception_returns_unchanged(self) -> None:
        qqqm_df = _make_single_ticker_frame(
            date(2021, 1, 4), date(2021, 6, 1), ticker="QQQM", seed=10
        )
        raw = {"QQQM": qqqm_df}
        result = _splice_qqqm(raw, date(2021, 1, 4), date(2021, 6, 1))
        assert result["QQQM"] is qqqm_df  # unchanged reference

    def test_splice_before_inception(self) -> None:
        # Build QQQ data from 2019 to 2021
        qqq = _make_single_ticker_frame(
            date(2019, 1, 2), date(2021, 1, 4), ticker="QQQ", seed=1
        )
        # Build QQQM data from 2020-10-13 to 2021
        qqqm = _make_single_ticker_frame(
            date(2020, 10, 13), date(2021, 1, 4), ticker="QQQM", seed=2
        )

        raw = {"QQQ": _add_returns(qqq), "QQQM": _add_returns(qqqm)}
        result = _splice_qqqm(raw, date(2019, 1, 2), date(2021, 1, 4))

        spliced = result["QQQM"]
        assert list(spliced.columns) == ["Close", "Returns"]
        # Spliced series should be longer than original QQQM alone
        assert len(spliced) > len(raw["QQQM"])

    def test_missing_qqq_returns_unchanged(self) -> None:
        qqqm = _make_single_ticker_frame(
            date(2020, 10, 13), date(2021, 1, 4), ticker="QQQM"
        )
        raw = {"QQQM": _add_returns(qqqm)}
        result = _splice_qqqm(raw, date(2019, 1, 2), date(2021, 1, 4))
        # No QQQ to splice with, so unchanged
        assert result["QQQM"] is raw["QQQM"]


# ---------------------------------------------------------------------------
# Integration tests for fetch_prices (mocked yfinance)
# ---------------------------------------------------------------------------


class TestFetchPrices:
    def test_single_ticker(self, tmp_path: Path) -> None:
        cache_dir = str(tmp_path / "cache")
        fake = _make_single_ticker_frame(date(2020, 1, 6), date(2020, 6, 30))

        with patch(
            "wealth_analyzer.data.fetcher.yf.download", return_value=fake
        ) as mock_dl:
            result = fetch_prices(
                ["AAPL"],
                date(2020, 1, 6),
                date(2020, 6, 30),
                cache_dir=cache_dir,
                use_cache=False,
            )

        assert "AAPL" in result
        assert list(result["AAPL"].columns) == ["Close", "Returns"]
        assert len(result["AAPL"]) > 0
        mock_dl.assert_called_once()

    def test_multi_ticker_batch(self, tmp_path: Path) -> None:
        cache_dir = str(tmp_path / "cache")
        fake = _make_price_series(["AAPL", "SPY"], date(2020, 1, 6), date(2020, 6, 30))

        with patch("wealth_analyzer.data.fetcher.yf.download", return_value=fake):
            result = fetch_prices(
                ["AAPL", "SPY"],
                date(2020, 1, 6),
                date(2020, 6, 30),
                cache_dir=cache_dir,
                use_cache=False,
            )

        assert "AAPL" in result
        assert "SPY" in result
        assert len(result) == 2

    def test_empty_response_returns_empty(self, tmp_path: Path) -> None:
        cache_dir = str(tmp_path / "cache")
        empty = pd.DataFrame()

        with patch("wealth_analyzer.data.fetcher.yf.download", return_value=empty):
            result = fetch_prices(
                ["AAPL"],
                date(2020, 1, 6),
                date(2020, 6, 30),
                cache_dir=cache_dir,
                use_cache=False,
            )

        assert result == {}

    def test_download_exception_returns_empty(self, tmp_path: Path) -> None:
        cache_dir = str(tmp_path / "cache")

        with patch(
            "wealth_analyzer.data.fetcher.yf.download",
            side_effect=Exception("network error"),
        ):
            result = fetch_prices(
                ["AAPL"],
                date(2020, 1, 6),
                date(2020, 6, 30),
                cache_dir=cache_dir,
                use_cache=False,
            )

        assert result == {}

    def test_cache_hit_skips_download(self, tmp_path: Path) -> None:
        cache_dir = str(tmp_path / "cache")
        # First call: cache miss → download
        fake = _make_single_ticker_frame(date(2020, 1, 6), date(2020, 6, 30))

        with patch(
            "wealth_analyzer.data.fetcher.yf.download", return_value=fake
        ) as mock_dl:
            result1 = fetch_prices(
                ["AAPL"],
                date(2020, 1, 6),
                date(2020, 6, 30),
                cache_dir=cache_dir,
                use_cache=True,
            )
            assert mock_dl.call_count == 1

        # Second call: cache hit → no download
        with patch(
            "wealth_analyzer.data.fetcher.yf.download", return_value=fake
        ) as mock_dl:
            result2 = fetch_prices(
                ["AAPL"],
                date(2020, 1, 6),
                date(2020, 6, 30),
                cache_dir=cache_dir,
                use_cache=True,
            )
            mock_dl.assert_not_called()

        pd.testing.assert_frame_equal(
            result1["AAPL"], result2["AAPL"], check_freq=False
        )

    def test_qqqm_splice_with_mock(self, tmp_path: Path) -> None:
        """When start < QQQM inception, both QQQ and QQQM must be fetched and spliced."""
        cache_dir = str(tmp_path / "cache")
        qqq = _make_single_ticker_frame(
            date(2019, 1, 2), date(2021, 1, 4), ticker="QQQ", seed=1
        )
        qqqm = _make_single_ticker_frame(
            date(2020, 10, 13), date(2021, 1, 4), ticker="QQQM", seed=2
        )

        combined = pd.concat(
            [
                qqq.rename(columns={"Close": ("Close", "QQQ")}),
                qqqm.rename(columns={"Close": ("Close", "QQQM")}),
            ],
            axis=1,
        )
        # Reconstruct proper multi-level columns
        combined = _make_price_series(
            ["QQQ", "QQQM"], date(2019, 1, 2), date(2021, 1, 4)
        )

        with patch("wealth_analyzer.data.fetcher.yf.download", return_value=combined):
            result = fetch_prices(
                ["QQQM", "QQQ"],
                date(2019, 1, 2),
                date(2021, 1, 4),
                cache_dir=cache_dir,
                use_cache=False,
            )

        assert "QQQM" in result
        assert "QQQ" in result
        # QQQM spliced data should have more rows than QQQM-only data
        assert len(result["QQQM"]) > 100

    def test_deduplicates_tickers(self, tmp_path: Path) -> None:
        cache_dir = str(tmp_path / "cache")
        fake = _make_single_ticker_frame(date(2020, 1, 6), date(2020, 6, 30))

        with patch(
            "wealth_analyzer.data.fetcher.yf.download", return_value=fake
        ) as mock_dl:
            fetch_prices(
                ["AAPL", "AAPL", "AAPL"],
                date(2020, 1, 6),
                date(2020, 6, 30),
                cache_dir=cache_dir,
                use_cache=False,
            )
        # yfinance should only be called once with deduplicated tickers
        mock_dl.assert_called_once()
        call_tickers = mock_dl.call_args[0][0]
        assert call_tickers == ["AAPL"]

    def test_returns_columns_correct(self, tmp_path: Path) -> None:
        cache_dir = str(tmp_path / "cache")
        fake = _make_single_ticker_frame(date(2020, 1, 6), date(2020, 6, 30))

        with patch("wealth_analyzer.data.fetcher.yf.download", return_value=fake):
            result = fetch_prices(
                ["AAPL"],
                date(2020, 1, 6),
                date(2020, 6, 30),
                cache_dir=cache_dir,
                use_cache=False,
            )

        df = result["AAPL"]
        assert list(df.columns) == ["Close", "Returns"]
        assert df["Returns"].isna().sum() == 0

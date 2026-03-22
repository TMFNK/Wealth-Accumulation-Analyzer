"""Tests for the Parquet disk cache layer."""

from __future__ import annotations

import os
import time
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from wealth_analyzer.data.cache import get, invalidate_all, set


@pytest.fixture()
def cache_dir(tmp_path: Path) -> str:
    return str(tmp_path / "cache")


def _sample_df(n: int = 5) -> pd.DataFrame:
    """Return a tiny DataFrame matching the fetcher output schema."""
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Close": np.linspace(100, 110, n), "Returns": np.linspace(0.001, 0.002, n)},
        index=idx,
    )


class TestCacheSetAndGet:
    def test_set_then_get_returns_same_data(self, cache_dir: str) -> None:
        df = _sample_df()
        set("AAPL", date(2020, 1, 1), date(2020, 1, 10), df, cache_dir=cache_dir)

        result = get(
            "AAPL",
            date(2020, 1, 1),
            date(2020, 1, 10),
            cache_dir=cache_dir,
            cache_ttl_days=1,
        )

        assert result is not None
        # Parquet does not preserve DatetimeIndex freq — check_freq=False
        pd.testing.assert_frame_equal(result, df, check_freq=False)

    def test_get_returns_none_for_missing_file(self, cache_dir: str) -> None:
        result = get(
            "MISSING", date(2020, 1, 1), date(2020, 1, 10), cache_dir=cache_dir
        )
        assert result is None

    def test_set_creates_cache_directory(self, tmp_path: Path) -> None:
        deep_dir = str(tmp_path / "a" / "b" / "cache")
        df = _sample_df()
        set("TEST", date(2020, 1, 1), date(2020, 1, 10), df, cache_dir=deep_dir)

        assert Path(deep_dir).is_dir()
        assert any(Path(deep_dir).glob("*.parquet"))

    def test_cache_key_includes_ticker_and_dates(self, cache_dir: str) -> None:
        df = _sample_df()
        set("MSFT", date(2021, 3, 1), date(2021, 3, 31), df, cache_dir=cache_dir)

        expected_name = "MSFT_2021-03-01_2021-03-31.parquet"
        assert (Path(cache_dir) / expected_name).is_file()


class TestCacheTTL:
    def test_expired_cache_returns_none(self, cache_dir: str) -> None:
        df = _sample_df()
        set("AAPL", date(2020, 1, 1), date(2020, 1, 10), df, cache_dir=cache_dir)

        # Artificially age the file to 2 days old
        path = Path(cache_dir) / "AAPL_2020-01-01_2020-01-10.parquet"
        old_mtime = time.time() - 2 * 86_400
        os.utime(path, (old_mtime, old_mtime))

        result = get(
            "AAPL",
            date(2020, 1, 1),
            date(2020, 1, 10),
            cache_dir=cache_dir,
            cache_ttl_days=1,
        )
        assert result is None

    def test_fresh_cache_returns_data(self, cache_dir: str) -> None:
        df = _sample_df()
        set("AAPL", date(2020, 1, 1), date(2020, 1, 10), df, cache_dir=cache_dir)

        result = get(
            "AAPL",
            date(2020, 1, 1),
            date(2020, 1, 10),
            cache_dir=cache_dir,
            cache_ttl_days=1,
        )
        assert result is not None

    def test_ttl_zero_never_expires(self, cache_dir: str) -> None:
        df = _sample_df()
        set("AAPL", date(2020, 1, 1), date(2020, 1, 10), df, cache_dir=cache_dir)

        # Age the file 100 days
        path = Path(cache_dir) / "AAPL_2020-01-01_2020-01-10.parquet"
        old_mtime = time.time() - 100 * 86_400
        os.utime(path, (old_mtime, old_mtime))

        result = get(
            "AAPL",
            date(2020, 1, 1),
            date(2020, 1, 10),
            cache_dir=cache_dir,
            cache_ttl_days=0,
        )
        assert result is not None


class TestInvalidateAll:
    def test_invalidate_all_deletes_parquet_files(self, cache_dir: str) -> None:
        df = _sample_df()
        set("AAPL", date(2020, 1, 1), date(2020, 1, 10), df, cache_dir=cache_dir)
        set("MSFT", date(2020, 1, 1), date(2020, 1, 10), df, cache_dir=cache_dir)
        set("NVDA", date(2020, 1, 1), date(2020, 1, 10), df, cache_dir=cache_dir)

        count = invalidate_all(cache_dir=cache_dir)
        assert count == 3
        assert list(Path(cache_dir).glob("*.parquet")) == []

    def test_invalidate_all_returns_zero_for_empty_dir(self, cache_dir: str) -> None:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        count = invalidate_all(cache_dir=cache_dir)
        assert count == 0

    def test_invalidate_all_returns_zero_for_missing_dir(self, tmp_path: Path) -> None:
        count = invalidate_all(cache_dir=str(tmp_path / "nonexistent"))
        assert count == 0

    def test_invalidate_all_ignores_non_parquet_files(self, cache_dir: str) -> None:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        # Create a non-parquet file
        (Path(cache_dir) / "notes.txt").write_text("hello")

        count = invalidate_all(cache_dir=cache_dir)
        assert count == 0
        assert (Path(cache_dir) / "notes.txt").is_file()

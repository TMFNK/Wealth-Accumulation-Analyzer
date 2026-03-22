"""Market data fetching from Yahoo Finance with optional disk cache."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from wealth_analyzer.data import cache as _cache

logger = logging.getLogger(__name__)

# QQQM inception as a QQQM proxy boundary.
_QQQM_INCEPTION = date(2020, 10, 13)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Sort index, drop duplicate dates, drop NaN rows."""
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="first")]
    df = df.dropna()
    return df


def _add_returns(df: pd.DataFrame) -> pd.DataFrame:
    """Add a ``Returns`` column as log-returns of ``Close``."""
    df = df.copy()
    df["Returns"] = np.log(df["Close"] / df["Close"].shift(1))
    df = df.dropna(subset=["Returns"])
    return df


def _extract_close(raw: Any, tickers: list[str]) -> dict[str, pd.DataFrame]:
    """Extract per-ticker Close DataFrames from yfinance output.

    yfinance returns different shapes depending on the number of tickers:
    - Single ticker: flat DataFrame with ``Close`` column
    - Multiple tickers: multi-level columns ``(field, ticker)``
    """
    out: dict[str, pd.DataFrame] = {}

    if len(tickers) == 1:
        t = tickers[0]
        if isinstance(raw, pd.DataFrame) and "Close" in raw.columns:
            out[t] = raw[["Close"]].copy()
        return out

    # Multi-ticker: columns are (field, ticker)
    if not isinstance(raw.columns, pd.MultiIndex):
        # Fallback: maybe only one ticker returned data
        if "Close" in raw.columns:
            out[tickers[0]] = raw[["Close"]].copy()
        return out

    close_frame = raw.get("Close")
    if close_frame is None or not isinstance(close_frame, pd.DataFrame):
        return out

    for t in tickers:
        if t in close_frame.columns:
            out[t] = close_frame[[t]].copy()
            out[t].columns = ["Close"]
    return out


def _splice_qqqm(
    raw: dict[str, pd.DataFrame],
    start: date,
    end: date,
) -> dict[str, pd.DataFrame]:
    """Replace QQQM data with a QQQ -> QQQM splice when *start* is before QQQM inception.

    The returned dict always stores the spliced series under the key ``"QQQM"``.
    """
    if "QQQM" not in raw:
        return raw

    if start >= _QQQM_INCEPTION:
        return raw

    qqq_df = raw.get("QQQ")
    qqqm_df = raw.get("QQQM")

    if qqq_df is None or qqq_df.empty or qqqm_df is None or qqqm_df.empty:
        logger.warning("Cannot splice QQQM: missing QQQ or QQQM data")
        return raw

    # Split QQQ data before QQQM inception
    qqq_before = qqq_df.loc[: _QQQM_INCEPTION.isoformat()].iloc[:-1]

    # Normalize QQQM so its first price matches QQQ's last price (continuous series)
    qqqm_after = qqqm_df.loc[_QQQM_INCEPTION.isoformat() :].copy()
    if qqqm_after.empty:
        logger.warning("QQQM has no data on or after %s", _QQQM_INCEPTION)
        return raw

    qqq_last_close = float(qqq_before["Close"].iloc[-1])
    qqqm_first_close = float(qqqm_after["Close"].iloc[0])
    scale = qqq_last_close / qqqm_first_close

    qqqm_after["Close"] = qqqm_after["Close"] * scale

    # Concatenate and recompute returns
    spliced: pd.DataFrame = pd.concat([qqq_before, qqqm_after])
    spliced = spliced[~spliced.index.duplicated(keep="first")]
    spliced = spliced.sort_index()
    spliced = _add_returns(spliced)

    result = dict(raw)
    result["QQQM"] = spliced[["Close", "Returns"]]
    logger.info(
        "Spliced QQQM: %d rows from QQQ + %d rows from QQQM (scale=%.6f)",
        len(qqq_before),
        len(qqqm_after),
        scale,
    )
    return result


def fetch_prices(
    tickers: list[str],
    start: date,
    end: date,
    *,
    cache_dir: str = "outputs/cache",
    cache_ttl_days: int = 1,
    use_cache: bool = True,
) -> dict[str, pd.DataFrame]:
    """Fetch dividend-adjusted prices for *tickers* from Yahoo Finance.

    Parameters
    ----------
    tickers:
        List of ticker symbols to download.
    start, end:
        Date range (inclusive).  An exclusive ``end + 1 day`` is passed to
        ``yfinance.download`` so that *end* itself is included when it is a
        trading day.
    cache_dir:
        Directory for Parquet cache files.
    cache_ttl_days:
        Cache time-to-live in days (``0`` disables expiry).
    use_cache:
        If ``True``, check the disk cache before hitting the network.

    Returns
    -------
    dict[str, pd.DataFrame]
        Mapping of ticker -> DataFrame with columns ``["Close", "Returns"]``.
        Tickers that fail are silently excluded (a warning is logged).
    """
    all_tickers = list(dict.fromkeys(tickers))  # preserve order, deduplicate
    result: dict[str, pd.DataFrame] = {}

    # --- Phase 1: check cache -------------------------------------------
    uncached: list[str] = []
    for ticker in all_tickers:
        if use_cache:
            cached = _cache.get(
                ticker, start, end, cache_dir=cache_dir, cache_ttl_days=cache_ttl_days
            )
            if cached is not None and not cached.empty:
                result[ticker] = cached
                continue
        uncached.append(ticker)

    if not uncached:
        logger.info("All %d ticker(s) served from cache", len(result))
        return _splice_qqqm(result, start, end)

    # --- Phase 2: batch download ----------------------------------------
    # Pass exclusive end = end + 1 day so yfinance includes the end date.
    exclusive_end = end + timedelta(days=1)
    logger.info(
        "Downloading %d ticker(s) from Yahoo Finance: %s",
        len(uncached),
        ", ".join(uncached),
    )

    try:
        raw = yf.download(
            uncached,
            start=start.isoformat(),
            end=exclusive_end.isoformat(),
            auto_adjust=True,
            actions=False,
            progress=False,
            group_by="column",
            threads=True,
        )
    except Exception:
        logger.exception("yfinance.download failed for %s", uncached)
        return _splice_qqqm(result, start, end)

    if not isinstance(raw, pd.DataFrame) or raw.empty:
        logger.warning("yfinance returned empty data for %s", uncached)
        return _splice_qqqm(result, start, end)

    # --- Phase 3: split multi-ticker frame into per-ticker DataFrames ---
    per_ticker = _extract_close(raw, uncached)

    for ticker in uncached:
        if ticker not in per_ticker:
            logger.warning("Ticker %s not in yfinance response — skipping", ticker)
            continue
        try:
            ticker_df = _normalize(per_ticker[ticker])

            if ticker_df.empty or ticker_df["Close"].isna().all():
                logger.warning("Ticker %s produced no usable data — skipping", ticker)
                continue

            ticker_df = _add_returns(ticker_df)
            result[ticker] = ticker_df[["Close", "Returns"]]

            # Persist to cache
            _cache.set(ticker, start, end, result[ticker], cache_dir=cache_dir)
            logger.debug("Fetched %s: %d rows", ticker, len(result[ticker]))
        except Exception:
            logger.warning(
                "Failed to process ticker %s — skipping", ticker, exc_info=True
            )

    return _splice_qqqm(result, start, end)

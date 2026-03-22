"""Disk cache for downloaded market data using Parquet files."""

from __future__ import annotations

import logging
import time
from datetime import date
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = "outputs/cache"


def _cache_key(ticker: str, start: date, end: date) -> str:
    """Build the Parquet filename for a ticker + date range."""
    return f"{ticker}_{start.isoformat()}_{end.isoformat()}.parquet"


def get(
    ticker: str,
    start: date,
    end: date,
    *,
    cache_dir: str = _DEFAULT_CACHE_DIR,
    cache_ttl_days: int = 1,
) -> pd.DataFrame | None:
    """Return cached DataFrame if it exists and is fresh, else ``None``.

    Parameters
    ----------
    ticker:
        Ticker symbol (used to build the cache filename).
    start, end:
        Date range that was fetched.
    cache_dir:
        Directory containing ``.parquet`` cache files.
    cache_ttl_days:
        Maximum age in days before a cached file is considered stale.
        A value of ``0`` means the cache never expires.

    Returns
    -------
    pd.DataFrame | None
        The cached DataFrame, or ``None`` if missing / expired.
    """
    path = Path(cache_dir) / _cache_key(ticker, start, end)
    if not path.is_file():
        return None

    if cache_ttl_days > 0:
        age_seconds = time.time() - path.stat().st_mtime
        ttl_seconds = cache_ttl_days * 86_400
        if age_seconds > ttl_seconds:
            logger.debug(
                "Cache expired for %s (age=%.0fs, ttl=%ds)",
                ticker,
                age_seconds,
                ttl_seconds,
            )
            return None

    try:
        df = pd.read_parquet(path, engine="pyarrow")
        logger.debug("Cache hit for %s (%d rows)", ticker, len(df))
        return df
    except Exception:
        logger.warning("Corrupt cache file %s — ignoring", path)
        return None


def set(
    ticker: str,
    start: date,
    end: date,
    df: pd.DataFrame,
    *,
    cache_dir: str = _DEFAULT_CACHE_DIR,
) -> None:
    """Persist *df* to the Parquet cache.

    Parent directories are created automatically.
    """
    path = Path(cache_dir) / _cache_key(ticker, start, end)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, engine="pyarrow")
    logger.debug("Cached %s → %s (%d rows)", ticker, path, len(df))


def invalidate_all(cache_dir: str = _DEFAULT_CACHE_DIR) -> int:
    """Delete every ``.parquet`` file in *cache_dir*.

    Returns the number of files deleted.
    """
    directory = Path(cache_dir)
    if not directory.is_dir():
        return 0

    deleted = 0
    for path in directory.glob("*.parquet"):
        try:
            path.unlink()
            deleted += 1
        except OSError:
            logger.warning("Failed to delete cache file %s", path)
    logger.info("Invalidated %d cache file(s) in %s", deleted, directory)
    return deleted

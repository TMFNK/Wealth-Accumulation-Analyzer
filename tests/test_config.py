from __future__ import annotations

from datetime import date
from pathlib import Path
from textwrap import dedent

import pytest
from pydantic import ValidationError

from wealth_analyzer.config import AppConfig, load_config


def _write_config(tmp_path: Path, *, general: str, investment: str | None = None) -> Path:
    investment_block = investment or dedent(
        """
        [investment]
        lump_sum_amount = 10000
        dca_monthly_amount = 500
        risk_free_rate = 0.045
        """
    ).strip()

    config_text = dedent(
        f"""
        [general]
        {general.strip()}

        {investment_block}

        [tickers]
        stocks = ["AAPL", "MSFT"]
        etfs = ["QQQM", "SPY"]

        [output]
        output_dir = "outputs"
        chart_dpi = 150
        excel_filename = "wealth_analysis_{{date}}.xlsx"
        pdf_filename = "wealth_analysis_{{date}}.pdf"
        log_level = "INFO"
        """
    ).strip()

    path = tmp_path / "config.toml"
    path.write_text(config_text)
    return path


def test_valid_config_loads(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        general="""
        start_date = "2013-01-01"
        end_date = "2025-03-01"
        cache_ttl_days = 1
        """,
    )

    config = load_config(str(path))

    assert isinstance(config, AppConfig)
    assert config.general.start_date == date(2013, 1, 1)
    assert config.general.end_date == date(2025, 3, 1)
    assert config.investment.lump_sum_amount == 10000


def test_start_date_after_end_date_raises_validation_error(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        general="""
        start_date = "2025-03-01"
        end_date = "2024-03-01"
        cache_ttl_days = 1
        """,
    )

    with pytest.raises(ValidationError):
        load_config(str(path))


def test_negative_lump_sum_amount_raises_validation_error(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        general="""
        start_date = "2013-01-01"
        end_date = "2025-03-01"
        cache_ttl_days = 1
        """,
        investment="""
        [investment]
        lump_sum_amount = -1
        dca_monthly_amount = 500
        risk_free_rate = 0.045
        """,
    )

    with pytest.raises(ValidationError):
        load_config(str(path))


def test_today_end_date_resolves_to_date(tmp_path: Path) -> None:
    path = _write_config(
        tmp_path,
        general="""
        start_date = "2013-01-01"
        end_date = "today"
        cache_ttl_days = 1
        """,
    )

    config = load_config(str(path))

    assert isinstance(config.general.end_date, date)
    assert config.general.end_date == date.today()


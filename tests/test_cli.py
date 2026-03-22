"""Tests for CLI entry points."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from click.testing import CliRunner

from wealth_analyzer.cli import (
    run_analysis,
    run_fetch,
    run_clear_cache,
    run_list_tickers,
)


def _make_config_path(tmp_path: Path) -> str:
    cfg_text = """
[general]
start_date = "2019-01-02"
end_date = "2023-12-29"
cache_ttl_days = 1

[investment]
lump_sum_amount = 10000
dca_monthly_amount = 500
risk_free_rate = 0.045

[tickers]
stocks = ["AAPL"]
etfs = ["SPY"]

[output]
output_dir = "{output_dir}"
chart_dpi = 72
excel_filename = "wealth_analysis_{{date}}.xlsx"
pdf_filename = "wealth_analysis_{{date}}.pdf"
log_level = "INFO"
""".format(output_dir=str(tmp_path / "outputs"))
    path = tmp_path / "config.toml"
    path.write_text(cfg_text)
    return str(path)


def _fake_prices() -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2019-01-02", periods=200)
    close = 100 + rng.standard_normal(200).cumsum() * 2
    close = np.abs(close) + 50
    s = pd.Series(close, index=dates, name="Close")
    log_ret = np.log(s / s.shift(1)).dropna()
    s = s.loc[log_ret.index]
    return {
        "AAPL": pd.DataFrame({"Close": s, "Returns": log_ret}),
        "SPY": pd.DataFrame({"Close": s * 1.1, "Returns": log_ret}),
    }


def _fake_ls_results() -> pd.DataFrame:
    return pd.DataFrame([{"ticker": "AAPL", "benchmark": "SPY", "cagr": 0.25}])


def _fake_growth() -> pd.DataFrame:
    dates = pd.bdate_range("2019-01-02", periods=200)
    return pd.DataFrame({"AAPL": np.linspace(10000, 15000, 200)}, index=dates)


def _fake_dca_results() -> pd.DataFrame:
    return pd.DataFrame([{"ticker": "AAPL", "xirr_pct": 0.12}])


class TestRunAnalysis:
    def test_exits_0_mocked(self, tmp_path: Path) -> None:
        config_path = _make_config_path(tmp_path)
        runner = CliRunner()
        prices = _fake_prices()
        growth = _fake_growth()

        with (
            patch("wealth_analyzer.data.fetcher.fetch_prices", return_value=prices),
            patch(
                "wealth_analyzer.analysis.lump_sum.run_lump_sum",
                return_value=(_fake_ls_results(), growth),
            ),
            patch(
                "wealth_analyzer.analysis.dca.run_dca",
                return_value=(_fake_dca_results(), growth, growth * 0.8),
            ),
            patch(
                "wealth_analyzer.reports.excel.write_excel",
                return_value=tmp_path / "fake.xlsx",
            ),
            patch(
                "wealth_analyzer.reports.pdf.write_pdf",
                return_value=tmp_path / "fake.pdf",
            ),
        ):
            result = runner.invoke(run_analysis, ["-c", config_path])
        assert result.exit_code == 0

    def test_exits_1_on_fetch_exception(self, tmp_path: Path) -> None:
        config_path = _make_config_path(tmp_path)
        runner = CliRunner()
        with patch(
            "wealth_analyzer.data.fetcher.fetch_prices", side_effect=Exception("boom")
        ):
            result = runner.invoke(run_analysis, ["-c", config_path])
        assert result.exit_code == 1

    def test_no_excel_skips(self, tmp_path: Path) -> None:
        config_path = _make_config_path(tmp_path)
        runner = CliRunner()
        prices = _fake_prices()
        growth = _fake_growth()

        with (
            patch("wealth_analyzer.data.fetcher.fetch_prices", return_value=prices),
            patch(
                "wealth_analyzer.analysis.lump_sum.run_lump_sum",
                return_value=(_fake_ls_results(), growth),
            ),
            patch(
                "wealth_analyzer.analysis.dca.run_dca",
                return_value=(_fake_dca_results(), growth, growth * 0.8),
            ),
            patch("wealth_analyzer.reports.excel.write_excel") as mock_excel,
        ):
            result = runner.invoke(
                run_analysis, ["-c", config_path, "--no-excel", "--no-pdf"]
            )
        mock_excel.assert_not_called()
        assert result.exit_code == 0

    def test_no_pdf_skips(self, tmp_path: Path) -> None:
        config_path = _make_config_path(tmp_path)
        runner = CliRunner()
        prices = _fake_prices()
        growth = _fake_growth()

        with (
            patch("wealth_analyzer.data.fetcher.fetch_prices", return_value=prices),
            patch(
                "wealth_analyzer.analysis.lump_sum.run_lump_sum",
                return_value=(_fake_ls_results(), growth),
            ),
            patch(
                "wealth_analyzer.analysis.dca.run_dca",
                return_value=(_fake_dca_results(), growth, growth * 0.8),
            ),
            patch(
                "wealth_analyzer.reports.excel.write_excel",
                return_value=tmp_path / "fake.xlsx",
            ),
            patch("wealth_analyzer.reports.pdf.write_pdf") as mock_pdf,
        ):
            result = runner.invoke(run_analysis, ["-c", config_path, "--no-pdf"])
        mock_pdf.assert_not_called()
        assert result.exit_code == 0

    def test_no_terminal_skips(self, tmp_path: Path) -> None:
        config_path = _make_config_path(tmp_path)
        runner = CliRunner()
        prices = _fake_prices()
        growth = _fake_growth()

        with (
            patch("wealth_analyzer.data.fetcher.fetch_prices", return_value=prices),
            patch(
                "wealth_analyzer.analysis.lump_sum.run_lump_sum",
                return_value=(_fake_ls_results(), growth),
            ),
            patch(
                "wealth_analyzer.analysis.dca.run_dca",
                return_value=(_fake_dca_results(), growth, growth * 0.8),
            ),
            patch("wealth_analyzer.reports.terminal.print_lump_sum_summary") as mock_ls,
            patch("wealth_analyzer.reports.terminal.print_dca_summary") as mock_dca,
        ):
            result = runner.invoke(
                run_analysis,
                ["-c", config_path, "--no-terminal", "--no-pdf", "--no-excel"],
            )
        mock_ls.assert_not_called()
        mock_dca.assert_not_called()
        assert result.exit_code == 0

    def test_exits_2_config_not_found(self) -> None:
        runner = CliRunner()
        result = runner.invoke(run_analysis, ["-c", "/nonexistent/config.toml"])
        assert result.exit_code == 2


class TestRunFetch:
    def test_exits_0(self, tmp_path: Path) -> None:
        config_path = _make_config_path(tmp_path)
        runner = CliRunner()
        with patch(
            "wealth_analyzer.data.fetcher.fetch_prices", return_value=_fake_prices()
        ):
            result = runner.invoke(run_fetch, ["-c", config_path])
        assert result.exit_code == 0
        assert "Cached" in result.output


class TestRunClearCache:
    def test_exits_0(self) -> None:
        runner = CliRunner()
        with patch("wealth_analyzer.data.cache.invalidate_all", return_value=0):
            result = runner.invoke(run_clear_cache)
        assert result.exit_code == 0
        assert "Cache cleared" in result.output


class TestRunListTickers:
    def test_exits_0_prints_tickers(self, tmp_path: Path) -> None:
        config_path = _make_config_path(tmp_path)
        runner = CliRunner()
        result = runner.invoke(run_list_tickers, ["-c", config_path])
        assert result.exit_code == 0
        assert "AAPL" in result.output
        assert "SPY" in result.output

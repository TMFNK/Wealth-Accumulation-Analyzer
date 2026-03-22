"""Rich terminal output for lump-sum and DCA analysis summaries."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from rich.console import Console
from rich.rule import Rule
from rich.table import Table

from wealth_analyzer.config import AppConfig

logger = logging.getLogger(__name__)
_console = Console()


def _is_valid(v: object) -> bool:
    """Return True if *v* is a finite numeric value (not NaN, None, inf)."""
    if v is None:
        return False
    if isinstance(v, float):
        return np.isfinite(v)
    return isinstance(v, (int,))


def _fmt_dollar(v: object) -> str:
    if _is_valid(v):
        return f"${v:,.0f}"
    return "\u2014"


def _fmt_pct(v: object) -> str:
    if _is_valid(v):
        return f"{v * 100:.2f}%"
    return "\u2014"


def _fmt_ratio(v: object) -> str:
    if _is_valid(v):
        return f"{v:.3f}"
    return "\u2014"


def _fmt_pp(v: object) -> str:
    if _is_valid(v):
        return f"{v:+.2f}pp" if v >= 0 else f"{v:.2f}pp"
    return "\u2014"


def _fmt_date(v: object) -> str:
    if v is None:
        return "\u2014"
    if hasattr(v, "strftime"):
        return v.strftime("%b %Y")
    return str(v)


def print_lump_sum_summary(
    results_df: pd.DataFrame,
    cfg: AppConfig,
) -> None:
    """Print a Rich table summarising lump-sum analysis results.

    Parameters
    ----------
    results_df:
        Output of ``run_lump_sum()`` — one row per stock x ETF pair.
    cfg:
        Application configuration.
    """
    amount = cfg.investment.lump_sum_amount
    _console.print()
    _console.print(
        Rule(f"[bold]LUMP-SUM ANALYSIS \u2014 ${amount:,.0f} invested per ticker")
    )

    if results_df.empty:
        _console.print("[dim]No results to display.[/]")
        return

    # Sort by outperformance descending
    df = results_df.copy()
    if "outperformance_cagr_pp" in df.columns:
        df = df.sort_values(
            "outperformance_cagr_pp", ascending=False, na_position="last"
        )

    table = Table(show_header=True, header_style="bold white on #1F4E79")
    table.add_column("Ticker", style="bold")
    table.add_column("Benchmark")
    table.add_column("Years", justify="right")
    table.add_column("Invested", justify="right")
    table.add_column("Final Value", justify="right")
    table.add_column("Total Return %", justify="right")
    table.add_column("CAGR %", justify="right")
    table.add_column("Sharpe", justify="right")
    table.add_column("Max DD %", justify="right")
    table.add_column("vs Bench (pp)", justify="right")

    for _, row in df.iterrows():
        opp = row.get("outperformance_cagr_pp")
        if _is_valid(opp) and opp > 0:
            style = "green"
        elif _is_valid(opp) and opp < 0:
            style = "red"
        else:
            style = ""

        cagr = row.get("cagr")
        tr = row.get("total_return_pct")
        sharpe = row.get("sharpe")
        max_dd = row.get("max_drawdown_pct")

        table.add_row(
            str(row.get("ticker", "")),
            str(row.get("benchmark", "")),
            f"{row.get('years_analyzed', 0):.1f}"
            if _is_valid(row.get("years_analyzed"))
            else "\u2014",
            _fmt_dollar(amount),
            _fmt_dollar(amount * (1 + tr)) if _is_valid(tr) else "\u2014",
            _fmt_pct(tr),
            _fmt_pct(cagr),
            _fmt_ratio(sharpe),
            _fmt_pct(max_dd),
            _fmt_pp(opp),
            style=style,
        )

    _console.print(table)

    # Footer
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    starts = df.get("shared_start_date")
    ends = df.get("end_date")
    start_str = str(starts.min()) if starts is not None and len(starts) > 0 else "?"
    end_str = str(ends.max()) if ends is not None and len(ends) > 0 else "?"
    rf = cfg.investment.risk_free_rate
    _console.print(
        f"[dim]Run: {now} | Data: {start_str} \u2192 {end_str} | "
        f"Risk-free rate: {rf:.1%}[/]"
    )


def print_dca_summary(
    results_df: pd.DataFrame,
    cfg: AppConfig,
) -> None:
    """Print a Rich table summarising DCA analysis results.

    Parameters
    ----------
    results_df:
        Output of ``run_dca()`` — one row per ticker.
    cfg:
        Application configuration.
    """
    monthly = cfg.investment.dca_monthly_amount
    rf = cfg.investment.risk_free_rate
    _console.print()
    _console.print(Rule(f"[bold]DCA ANALYSIS \u2014 ${monthly:,.0f}/month"))

    if results_df.empty:
        _console.print("[dim]No results to display.[/]")
        return

    df = results_df.copy()
    if "xirr_pct" in df.columns:
        df = df.sort_values("xirr_pct", ascending=False, na_position="last")

    table = Table(show_header=True, header_style="bold white on #1F4E79")
    table.add_column("Ticker", style="bold")
    table.add_column("Invested", justify="right")
    table.add_column("Final Value", justify="right")
    table.add_column("XIRR %", justify="right")
    table.add_column("CAGR %", justify="right")
    table.add_column("Sharpe", justify="right")
    table.add_column("Sortino", justify="right")
    table.add_column("Max DD %", justify="right")
    table.add_column("Best Month")
    table.add_column("Worst Month")

    for _, row in df.iterrows():
        xirr_val = row.get("xirr_pct")
        if _is_valid(xirr_val) and xirr_val > rf:
            style = "green"
        elif _is_valid(xirr_val) and xirr_val < rf:
            style = "red"
        else:
            style = ""

        table.add_row(
            str(row.get("ticker", "")),
            _fmt_dollar(row.get("total_contributions")),
            _fmt_dollar(row.get("final_value")),
            _fmt_pct(xirr_val),
            _fmt_pct(row.get("cagr")),
            _fmt_ratio(row.get("sharpe")),
            _fmt_ratio(row.get("sortino")),
            _fmt_pct(row.get("max_drawdown_pct")),
            _fmt_date(row.get("best_entry_month")),
            _fmt_date(row.get("worst_entry_month")),
            style=style,
        )

    _console.print(table)

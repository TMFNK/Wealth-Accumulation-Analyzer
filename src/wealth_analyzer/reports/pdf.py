"""PDF report generation using ReportLab."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from wealth_analyzer.config import AppConfig
from wealth_analyzer.reports.charts import (
    _fig_to_image,
    dca_cost_basis_chart,
    drawdown_chart,
    monthly_returns_heatmap,
    wealth_growth_chart,
)

logger = logging.getLogger(__name__)

_HEX_DARK_BLUE = colors.HexColor("#1F4E79")
_HEX_ALT_ROW = colors.HexColor("#EBF0F7")


def _build_styles() -> dict:
    """Create custom ReportLab paragraph styles."""
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title2",
            parent=ss["Title"],
            fontSize=24,
            fontName="Helvetica-Bold",
            spaceAfter=12,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle2",
            parent=ss["Normal"],
            fontSize=14,
            fontName="Helvetica",
            textColor=colors.grey,
            spaceAfter=8,
        ),
        "heading": ParagraphStyle(
            "Heading2",
            parent=ss["Heading1"],
            fontSize=16,
            fontName="Helvetica-Bold",
            textColor=_HEX_DARK_BLUE,
            spaceAfter=8,
        ),
        "body": ParagraphStyle(
            "Body2", parent=ss["Normal"], fontSize=10, fontName="Helvetica", leading=14
        ),
    }


def _metric_table(data: list[list[str]], col_widths: list[float]) -> Table:
    """Create a styled 2-column metric table."""
    t = Table(data, colWidths=col_widths)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), _HEX_DARK_BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), _HEX_ALT_ROW))
    t.setStyle(TableStyle(style))
    return t


def _fmt(v: object, fmt_str: str = ".2f") -> str:
    """Format a value, returning em-dash for None/NaN."""
    if v is None:
        return "\u2014"
    if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
        return "\u2014"
    if fmt_str == "pct":
        return f"{v * 100:.2f}%"
    return f"{v:{fmt_str}}"


def write_pdf(
    lump_sum_results: pd.DataFrame,
    lump_sum_growth: pd.DataFrame,
    dca_results: pd.DataFrame,
    dca_growth: pd.DataFrame,
    dca_cost_basis: pd.DataFrame,
    prices: dict[str, pd.DataFrame],
    cfg: AppConfig,
) -> Path:
    """Write a multi-page PDF report.

    Parameters
    ----------
    lump_sum_results, lump_sum_growth:
        Outputs from ``run_lump_sum()``.
    dca_results, dca_growth, dca_cost_basis:
        Outputs from ``run_dca()``.
    prices:
        Mapping of ticker -> DataFrame (from ``fetch_prices``).
    cfg:
        Application configuration.

    Returns
    -------
    Path
        The path to the written PDF.
    """
    output_dir = Path(cfg.output.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = cfg.output.pdf_filename.replace("{date}", date.today().isoformat())
    path = output_dir / filename

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = _build_styles()
    story: list = []
    page_width = A4[0] - 4 * cm

    n_stocks = len(cfg.tickers.stocks)
    n_etfs = len(cfg.tickers.etfs)

    # --- Page 1: Title ---
    story.append(Spacer(1, 3 * cm))
    story.append(Paragraph("Wealth Accumulation Analysis", styles["title"]))
    story.append(Paragraph(f"Generated {date.today().isoformat()}", styles["subtitle"]))
    story.append(Spacer(1, 1 * cm))

    cfg_data = [
        ["Parameter", "Value"],
        ["Start Date", str(cfg.general.start_date)],
        ["End Date", str(cfg.general.end_date)],
        ["Lump Sum", f"${cfg.investment.lump_sum_amount:,.0f}"],
        ["DCA Monthly", f"${cfg.investment.dca_monthly_amount:,.0f}"],
        ["Risk-Free Rate", f"{cfg.investment.risk_free_rate:.1%}"],
        ["Stocks", ", ".join(cfg.tickers.stocks)],
        ["ETFs", ", ".join(cfg.tickers.etfs)],
    ]
    story.append(_metric_table(cfg_data, [page_width * 0.35, page_width * 0.65]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            f"This report compares lump-sum and DCA strategies across "
            f"{n_stocks} stocks and {n_etfs} ETF benchmarks. "
            f"All prices are dividend-adjusted.",
            styles["body"],
        )
    )
    story.append(PageBreak())

    # --- Lump-Sum Overview ---
    story.append(Paragraph("Lump-Sum Strategy Overview", styles["heading"]))
    story.append(
        Paragraph(
            f"${cfg.investment.lump_sum_amount:,.0f} invested per ticker on the first shared trading day.",
            styles["body"],
        )
    )
    story.append(Spacer(1, 0.5 * cm))

    if not lump_sum_growth.empty:
        fig = wealth_growth_chart(lump_sum_growth, cfg, title="Lump-Sum Wealth Growth")
        story.append(_fig_to_image(fig, cfg.output.chart_dpi))
    story.append(PageBreak())

    # --- Per-ticker deep dive ---
    for ticker in cfg.tickers.stocks:
        if ticker not in prices:
            continue

        story.append(Paragraph(f"{ticker} \u2014 Detailed Analysis", styles["heading"]))

        # Metrics table from lump_sum_results
        ticker_rows = (
            lump_sum_results[lump_sum_results["ticker"] == ticker]
            if not lump_sum_results.empty
            else pd.DataFrame()
        )
        if not ticker_rows.empty:
            first = ticker_rows.iloc[0]
            metrics_data = [
                ["Metric", "Value"],
                ["Total Return", _fmt(first.get("total_return_pct"), "pct")],
                ["CAGR", _fmt(first.get("cagr"), "pct")],
                ["Sharpe", _fmt(first.get("sharpe"))],
                ["Sortino", _fmt(first.get("sortino"))],
                ["Max Drawdown", _fmt(first.get("max_drawdown_pct"), "pct")],
                [
                    "Recovery Months",
                    _fmt(first.get("max_drawdown_recovery_months"), ".0f"),
                ],
                [
                    "Annualized Volatility",
                    _fmt(first.get("annualized_volatility"), "pct"),
                ],
            ]
            story.append(
                _metric_table(metrics_data, [page_width * 0.5, page_width * 0.5])
            )
            story.append(Spacer(1, 0.3 * cm))

            # Benchmark comparison table
            bench_rows = ticker_rows[
                ["benchmark", "benchmark_cagr", "cagr", "outperformance_cagr_pp"]
            ]
            if not bench_rows.empty:
                bench_data = [
                    ["Benchmark", "Stock CAGR", "Bench CAGR", "Outperform (pp)"]
                ]
                for _, br in bench_rows.iterrows():
                    bench_data.append(
                        [
                            str(br.get("benchmark", "")),
                            _fmt(br.get("cagr"), "pct"),
                            _fmt(br.get("benchmark_cagr"), "pct"),
                            _fmt(br.get("outperformance_cagr_pp"), ".2f"),
                        ]
                    )
                story.append(_metric_table(bench_data, [page_width * 0.25] * 4))
            story.append(Spacer(1, 0.3 * cm))

        # Drawdown chart
        if ticker in lump_sum_growth.columns:
            fig = drawdown_chart(
                lump_sum_growth[[ticker]], cfg, title=f"{ticker} Drawdown"
            )
            story.append(_fig_to_image(fig, cfg.output.chart_dpi))

        # Monthly heatmap
        fig = monthly_returns_heatmap(prices, ticker, cfg)
        story.append(_fig_to_image(fig, cfg.output.chart_dpi))
        story.append(PageBreak())

    # --- DCA Overview ---
    story.append(
        Paragraph(
            f"DCA Strategy Overview \u2014 ${cfg.investment.dca_monthly_amount:,.0f}/month",
            styles["heading"],
        )
    )
    if not dca_growth.empty and not dca_cost_basis.empty:
        fig = dca_cost_basis_chart(dca_growth, dca_cost_basis, cfg)
        story.append(_fig_to_image(fig, cfg.output.chart_dpi))
    story.append(PageBreak())

    # --- DCA Per-Ticker ---
    for ticker in cfg.tickers.stocks:
        if dca_results.empty or ticker not in dca_results["ticker"].values:
            continue

        story.append(Paragraph(f"{ticker} \u2014 DCA Results", styles["heading"]))
        row = dca_results[dca_results["ticker"] == ticker].iloc[0]
        dca_data = [
            ["Metric", "Value"],
            ["XIRR", _fmt(row.get("xirr_pct"), "pct")],
            ["Total Contributions", f"${row.get('total_contributions', 0):,.2f}"],
            ["Final Value", f"${row.get('final_value', 0):,.2f}"],
            ["Multiple on Invested", _fmt(row.get("multiple_on_invested"))],
            ["Best Entry Month", str(row.get("best_entry_month", "\u2014"))],
            ["Worst Entry Month", str(row.get("worst_entry_month", "\u2014"))],
            ["CAGR", _fmt(row.get("cagr"), "pct")],
            ["Sharpe", _fmt(row.get("sharpe"))],
            ["Max Drawdown", _fmt(row.get("max_drawdown_pct"), "pct")],
            ["Annualized Volatility", _fmt(row.get("annualized_volatility"), "pct")],
        ]
        story.append(_metric_table(dca_data, [page_width * 0.5, page_width * 0.5]))
        story.append(PageBreak())

    doc.build(story)
    logger.info("PDF report written to %s", path)
    return path

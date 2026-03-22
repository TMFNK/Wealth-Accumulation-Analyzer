"""Chart generation utilities for wealth accumulation analysis."""

from __future__ import annotations

import logging
from io import BytesIO

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from adjustText import adjust_text
from matplotlib.figure import Figure

from wealth_analyzer.config import AppConfig

logger = logging.getLogger(__name__)

# Pick best available style
_STYLE_CANDIDATES = ["seaborn-v0_8-darkgrid", "seaborn-darkgrid", "ggplot"]
for _s in _STYLE_CANDIDATES:
    if _s in plt.style.available:
        matplotlib.style.use(_s)
        break


def wealth_growth_chart(
    growth_df: pd.DataFrame,
    cfg: AppConfig,
    title: str = "Wealth Growth",
    highlight_tickers: list[str] | None = None,
) -> Figure:
    """Create a line chart of portfolio value over time.

    Parameters
    ----------
    growth_df:
        Time-indexed DataFrame with one column per ticker (from
        ``run_lump_sum`` or ``run_dca``).
    cfg:
        Application configuration.
    title:
        Chart title.
    highlight_tickers:
        If provided, these tickers get 2.5x linewidth; others get 0.6x opacity.

    Returns
    -------
    matplotlib.figure.Figure
    """
    fig, ax = plt.subplots(figsize=(12, 6), dpi=cfg.output.chart_dpi)
    etfs = set(cfg.tickers.etfs)
    texts: list = []

    for i, col in enumerate(growth_df.columns):
        series = growth_df[col].dropna()
        if series.empty:
            continue
        color = f"C{i % 10}"
        is_etf = col in etfs
        lw = 1.5
        ls = "--" if is_etf else "-"
        alpha = 1.0

        if highlight_tickers is not None:
            if col in highlight_tickers:
                lw = 2.5 * 1.5
            else:
                alpha = 0.6

        ax.plot(
            series.index,
            series.values,
            label=col,
            color=color,
            linestyle=ls,
            linewidth=lw,
            alpha=alpha,
        )

        # Annotate final value
        last_x = series.index[-1]
        last_y = series.iloc[-1]
        texts.append(
            ax.text(last_x, last_y, f"{col}: ${last_y:,.0f}", fontsize=7, color=color)
        )

    if texts:
        adjust_text(
            texts, ax=ax, arrowprops=dict(arrowstyle="->", color="gray", lw=0.8)
        )

    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Portfolio Value (USD, log scale)")
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda x, _: f"${x:,.0f}")
    )
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=8)
    fig.tight_layout()
    return fig


def drawdown_chart(
    growth_df: pd.DataFrame,
    cfg: AppConfig,
    title: str = "Drawdown Over Time",
) -> Figure:
    """Create a filled-area drawdown chart.

    Parameters
    ----------
    growth_df:
        Time-indexed DataFrame with one column per ticker.
    cfg:
        Application configuration.
    title:
        Chart title.

    Returns
    -------
    matplotlib.figure.Figure
    """
    fig, ax = plt.subplots(figsize=(12, 5), dpi=cfg.output.chart_dpi)
    all_min_dd = 0.0

    for i, col in enumerate(growth_df.columns):
        series = growth_df[col].dropna()
        if series.empty:
            continue
        rolling_max = series.cummax()
        dd = (series - rolling_max) / rolling_max * 100
        color = f"C{i % 10}"
        ax.fill_between(dd.index, dd.values, alpha=0.3, color=color, label=col)
        ax.plot(dd.index, dd.values, color=color, linewidth=0.8)
        min_dd = dd.min()
        if min_dd < all_min_dd:
            all_min_dd = min_dd

    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Drawdown %")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter())
    # Set lower limit with 10% padding
    if all_min_dd < 0:
        ax.set_ylim(bottom=all_min_dd * 1.1, top=2)
    ax.grid(axis="y")
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=8)
    fig.tight_layout()
    return fig


def dca_cost_basis_chart(
    growth_df: pd.DataFrame,
    cost_basis_df: pd.DataFrame,
    cfg: AppConfig,
) -> Figure:
    """Create per-ticker subplots showing portfolio value vs cost basis.

    Parameters
    ----------
    growth_df:
        DCA portfolio value DataFrame.
    cost_basis_df:
        Cumulative cost basis DataFrame.
    cfg:
        Application configuration.

    Returns
    -------
    matplotlib.figure.Figure
    """
    tickers = list(growth_df.columns)
    n = len(tickers)
    if n == 0:
        fig, _ = plt.subplots(figsize=(12, 4), dpi=cfg.output.chart_dpi)
        return fig

    ncols = min(n, 3)
    nrows = -(-n // ncols)  # ceil division
    fig, axes = plt.subplots(
        nrows,
        ncols,
        figsize=(6 * ncols, 4 * nrows),
        dpi=cfg.output.chart_dpi,
        squeeze=False,
    )
    axes_flat = axes.flatten()

    for i, ticker in enumerate(tickers):
        ax = axes_flat[i]
        gv = growth_df[ticker].dropna()
        cb = (
            cost_basis_df[ticker].dropna()
            if ticker in cost_basis_df.columns
            else pd.Series(dtype=float)
        )

        if not gv.empty:
            ax.plot(
                gv.index, gv.values, color="C0", linewidth=1.5, label="Portfolio Value"
            )
        if not cb.empty:
            ax.plot(
                cb.index,
                cb.values,
                color="C1",
                linewidth=1.2,
                linestyle="--",
                label="Cost Basis",
            )

        # Fill between for profit/loss zones
        if not gv.empty and not cb.empty:
            common = gv.index.intersection(cb.index)
            if len(common) > 0:
                gv_c = gv.loc[common]
                cb_c = cb.loc[common]
                ax.fill_between(
                    common, gv_c, cb_c, where=gv_c >= cb_c, alpha=0.15, color="green"
                )
                ax.fill_between(
                    common, gv_c, cb_c, where=gv_c < cb_c, alpha=0.15, color="red"
                )

        ax.set_title(ticker, fontsize=10, fontweight="bold")
        ax.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda x, _: f"${x:,.0f}")
        )
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%Y"))
        ax.legend(fontsize=7)

    # Hide unused axes
    for j in range(n, len(axes_flat)):
        axes_flat[j].set_visible(False)

    fig.suptitle("DCA Portfolio Value vs Cost Basis", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    return fig


def monthly_returns_heatmap(
    prices: dict[str, pd.DataFrame],
    ticker: str,
    cfg: AppConfig,
) -> Figure:
    """Create a monthly returns heatmap for a single ticker.

    Parameters
    ----------
    prices:
        Mapping of ticker -> DataFrame with ``["Close", "Returns"]``.
    ticker:
        The ticker to chart.
    cfg:
        Application configuration.

    Returns
    -------
    matplotlib.figure.Figure
    """
    fig, ax = plt.subplots(figsize=(10, 6), dpi=cfg.output.chart_dpi)

    if ticker not in prices:
        ax.text(
            0.5,
            0.5,
            f"No data for {ticker}",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        return fig

    returns = prices[ticker]["Returns"]
    monthly = returns.resample("ME").sum()

    # Pivot into year x month matrix
    monthly_df = pd.DataFrame(
        {
            "year": monthly.index.year,
            "month": monthly.index.month,
            "return": monthly.values,
        }
    )
    pivot = monthly_df.pivot_table(index="year", columns="month", values="return")

    month_labels = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]

    # Ensure all 12 months are columns
    for m in range(1, 13):
        if m not in pivot.columns:
            pivot[m] = np.nan
    pivot = pivot[sorted(pivot.columns)]

    im = ax.imshow(pivot.values, cmap="RdYlGn", vmin=-0.20, vmax=0.20, aspect="auto")

    # Annotate cells
    for row_idx in range(pivot.shape[0]):
        for col_idx in range(pivot.shape[1]):
            val = pivot.values[row_idx, col_idx]
            if not np.isnan(val):
                ax.text(
                    col_idx,
                    row_idx,
                    f"{val * 100:.1f}%",
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="black" if abs(val) < 0.10 else "white",
                )

    ax.set_xticks(range(12))
    ax.set_xticklabels(month_labels)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index.astype(int))
    ax.set_title(
        f"{ticker} \u2014 Monthly Log-Returns Heatmap", fontsize=14, fontweight="bold"
    )
    fig.colorbar(im, ax=ax, label="Log-Return", shrink=0.8)
    fig.tight_layout()
    return fig


def _fig_to_image(fig: Figure, dpi: int):
    """Convert a matplotlib Figure to a ReportLab Image flowable.

    The figure is closed after conversion to free memory.
    """
    from reportlab.platypus import Image

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)

    img = Image(buf, width=14 * 28.35, height=9 * 28.35)  # 14cm x 9cm in points
    img.hAlign = "CENTER"
    return img

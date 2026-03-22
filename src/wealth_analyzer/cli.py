"""CLI entry points for the wealth analyzer."""

from __future__ import annotations

import logging

import click
from rich.console import Console

from wealth_analyzer.config import load_config

console = Console()


@click.command()
@click.option(
    "-c",
    "--config",
    "config_path",
    default="config.toml",
    show_default=True,
    help="Path to config.toml",
)
@click.option("-o", "--output", default=None, help="Override output directory")
@click.option("--no-excel", is_flag=True, default=False, help="Skip Excel report")
@click.option("--no-pdf", is_flag=True, default=False, help="Skip PDF report")
@click.option("--no-terminal", is_flag=True, default=False, help="Skip terminal output")
@click.option("-t", "--tickers", multiple=True, help="Override stock tickers")
@click.option("-b", "--benchmarks", multiple=True, help="Override ETF benchmarks")
def run_analysis(
    config_path: str,
    output: str | None,
    no_excel: bool,
    no_pdf: bool,
    no_terminal: bool,
    tickers: tuple[str, ...],
    benchmarks: tuple[str, ...],
) -> None:
    """Run full wealth accumulation analysis."""
    try:
        cfg = load_config(config_path)
    except FileNotFoundError:
        console.print(f"[red]Error:[/] Config file not found: {config_path}")
        raise SystemExit(2) from None
    except Exception as exc:
        console.print(f"[red]Config error:[/] {exc}")
        raise SystemExit(2) from exc

    if output:
        cfg.output.output_dir = output
    if tickers:
        cfg.tickers.stocks = list(tickers)
    if benchmarks:
        cfg.tickers.etfs = list(benchmarks)

    # Setup logging
    log_level = getattr(logging, cfg.output.log_level.upper(), logging.INFO)
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    all_tickers = list(dict.fromkeys(cfg.tickers.stocks + cfg.tickers.etfs))

    from wealth_analyzer.data.fetcher import fetch_prices
    from wealth_analyzer.analysis.lump_sum import run_lump_sum
    from wealth_analyzer.analysis.dca import run_dca
    from wealth_analyzer.reports.terminal import (
        print_lump_sum_summary,
        print_dca_summary,
    )
    from wealth_analyzer.reports.excel import write_excel
    from wealth_analyzer.reports.pdf import write_pdf

    try:
        with console.status("Fetching price data\u2026"):
            prices = fetch_prices(
                all_tickers,
                cfg.general.start_date,
                cfg.general.end_date,
                cache_dir=f"{cfg.output.output_dir}/cache",
                cache_ttl_days=cfg.general.cache_ttl_days,
            )

        if not prices:
            console.print(
                "[red]Error:[/] No price data fetched. Check tickers and network."
            )
            raise SystemExit(3)

        console.print(f"[green]\u2713[/] Fetched {len(prices)} tickers")

        with console.status("Running lump-sum analysis\u2026"):
            ls_results, ls_growth = run_lump_sum(prices, cfg)

        with console.status("Running DCA analysis\u2026"):
            dca_results, dca_growth, dca_cost = run_dca(prices, cfg)

        if not no_terminal:
            print_lump_sum_summary(ls_results, cfg)
            print_dca_summary(dca_results, cfg)

        if not no_excel:
            with console.status("Writing Excel report\u2026"):
                excel_path = write_excel(
                    ls_results, ls_growth, dca_results, dca_growth, dca_cost, cfg
                )
                console.print(f"[green]\u2713[/] Excel \u2192 {excel_path}")

        if not no_pdf:
            with console.status("Writing PDF report\u2026"):
                pdf_path = write_pdf(
                    ls_results,
                    ls_growth,
                    dca_results,
                    dca_growth,
                    dca_cost,
                    prices,
                    cfg,
                )
                console.print(f"[green]\u2713[/] PDF \u2192 {pdf_path}")

    except SystemExit:
        raise
    except Exception:
        console.print_exception()
        raise SystemExit(1) from None


@click.command()
@click.option("-c", "--config", "config_path", default="config.toml", show_default=True)
def run_fetch(config_path: str) -> None:
    """Pre-fetch and cache price data without running analysis."""
    cfg = load_config(config_path)
    from wealth_analyzer.data.fetcher import fetch_prices

    all_tickers = list(dict.fromkeys(cfg.tickers.stocks + cfg.tickers.etfs))
    with console.status("Fetching\u2026"):
        prices = fetch_prices(
            all_tickers,
            cfg.general.start_date,
            cfg.general.end_date,
            cache_dir=f"{cfg.output.output_dir}/cache",
            cache_ttl_days=cfg.general.cache_ttl_days,
        )
    console.print(f"[green]\u2713[/] Cached {len(prices)} tickers.")


@click.command()
def run_clear_cache() -> None:
    """Delete all cached Parquet price files."""
    from wealth_analyzer.data.cache import invalidate_all

    count = invalidate_all()
    console.print(f"[yellow]Cache cleared.[/] ({count} files removed)")


@click.command()
@click.option("-c", "--config", "config_path", default="config.toml", show_default=True)
def run_list_tickers(config_path: str) -> None:
    """List configured stock and ETF tickers."""
    cfg = load_config(config_path)
    console.print("[bold]Stocks:[/]", ", ".join(cfg.tickers.stocks))
    console.print("[bold]ETFs:[/]", ", ".join(cfg.tickers.etfs))

# Wealth Accumulation Analyzer Design

## Goal

Build a Python CLI that compares long-term wealth accumulation for individual stocks versus a benchmark ETF using live historical price data. The first release is a single-ticker MVP that proves the full pipeline end to end before the project scales to multi-ticker comparison reports.

## Scope

### In Scope for the First Slice

- Fetch live dividend-adjusted historical data from Yahoo Finance via `yfinance`
- Validate that the chosen stock and benchmark have enough overlapping history
- Simulate a lump-sum investment from the first shared trading day
- Simulate monthly dollar-cost averaging with fractional shares
- Compute a small but useful metric set:
  - total return
  - CAGR
  - final portfolio value
  - annualized volatility
  - max drawdown
- Emit a terminal summary and a JSON or CSV result file
- Keep the code modular so later work can add charts, Excel, and PDF reports without rewriting the analysis core

### Explicitly Deferred

- Multi-ticker batch comparisons
- Excel workbook output
- PDF report generation
- PNG chart generation
- Caching layer
- Benchmarks beyond a single stock-versus-benchmark comparison

## Financial Model

### Price Series Convention

This MVP treats Yahoo Finance adjusted close as a practical total-return proxy. The analysis uses `yfinance.download(..., auto_adjust=True, actions=False, progress=False)` and treats the returned `Close` column as the adjusted close series. The index is converted to timezone-naive calendar dates before alignment. The analysis does not model separate dividend cashflows, ex-dividend timing, withholding taxes, commissions, or slippage.

Trades are executed at the adjusted close on the relevant execution date: `analysis_start` for the lump-sum purchase and each DCA deposit date for DCA.

### Lump-Sum Strategy

- Invest the configured lump-sum amount on `analysis_start`.
- Hold fractional shares.
- Measure performance from `analysis_start` through `analysis_end`.
- Define `days_elapsed = (analysis_end - analysis_start).days`.
- Report CAGR using `((final_value / investment_amount) ** (365 / days_elapsed)) - 1`.
- If `days_elapsed <= 0`, record CAGR as null and emit a warning.
- Report total return, final value, annualized volatility, max drawdown, and run metadata.

### DCA Strategy

- Invest the configured monthly amount on the first shared trading day of each month after the month containing `analysis_start`.
- If `analysis_start` falls on the first trading day of a month, that month is excluded from DCA deposits and DCA begins the following month.
- Include a month only if its first shared trading day is on or before `analysis_end`.
- If a month in the active window has no shared trading day after normalization, skip that contribution and emit a warning.
- If the first calendar day of a month is a weekend, holiday, or missing for one asset, use the first shared trading day in that month.
- Allow fractional shares.
- Use money-weighted return via XIRR as the primary return metric for DCA.
- Implement XIRR with `scipy.optimize.brentq` over discounted cash flows on the interval `[-0.9999, 10.0]`.
- Use Actual/365 day-count for the XIRR year fraction.
- Use the earliest cashflow date after combining same-day cashflows as `t0` for the Actual/365 year fraction.
- Use negative cash flows for contributions and a positive final liquidation value on `analysis_end`.
- Combine same-day cash flows before solving XIRR.
- If XIRR does not converge or has no valid root, record a null metric and emit a warning rather than failing the run.
- Report multiple on invested capital as `final_value / total_contributions`.

### Risk Metrics

- Annualized volatility is computed from the daily log returns of each asset's adjusted-close series restricted to `[analysis_start, analysis_end]` and annualized with `sqrt(252)`.
- Max drawdown and recovery time are computed on each asset's adjusted-close series restricted to `[analysis_start, analysis_end]`, not on the contribution-distorted portfolio value series.
- For a given ticker, risk metrics are identical for the lump-sum and DCA rows because they describe the asset series, not the cash-flow schedule.
- `recovery_months` is the number of calendar months between the peak date and the first later date that recovers that peak; if recovery never occurs by `analysis_end`, the value is null.

### Data Sufficiency

- Normalize each fetched series by sorting the index, dropping duplicate dates, and dropping NaNs before alignment.
- Fetch raw data over `[user_start_date, resolved_user_end_date]`, normalize it, and compute the shared calendar before defining the final analysis window.
- Set `analysis_start` to the first shared trading day on or after `user_start_date`.
- Set `analysis_end` to the earlier of the resolved user end date and the last shared trading day.
- Compute `shared_trading_days` as the intersection of normalized dates and `union_trading_days` as the union of normalized dates within `[analysis_start, analysis_end]`.
- Require `coverage = len(shared_trading_days) / len(union_trading_days) >= 0.95`.
- Require at least `252 * 5` shared trading rows between `analysis_start` and `analysis_end`.
- If these thresholds are not met, fail the run with a clear user-facing message and a nonzero exit code.

## Architecture

The application is organized as a small package under `src/wealth_analyzer/` with four clear responsibilities:

- `config.py` loads and validates runtime settings.
- `data/` fetches and normalizes price history.
- `analysis/` calculates investment outcomes and metrics.
- `reports/` formats results for the terminal and for export.

The initial CLI is intentionally thin. It should orchestrate the pipeline, not contain business logic. That keeps the data and analysis code independently testable and makes later report expansion low-risk.

The data layer should expose a mockable provider boundary, such as a `PriceHistoryProvider` protocol or equivalent function contract, so tests can swap live Yahoo Finance access for fixture-backed data without changing the analysis code.

## Data Flow

1. Load config from `config.toml` plus any CLI overrides.
2. Fetch live data for one stock and one benchmark, passing an exclusive `end` value that is one calendar day after the resolved user end date so the requested end date is included when it is a trading day.
3. Normalize and align both series on the shared calendar.
4. Set `analysis_start` to the first shared trading day on or after `start_date`.
5. Set `analysis_end` to the earlier of the user end date and the last shared trading day.
6. Run lump-sum and DCA simulations using adjusted close prices.
7. Calculate summary metrics for each strategy.
8. Print a compact comparison table.
9. Save a machine-readable result file for downstream use.

## Config Contract

The first slice should support a small, explicit config surface with the precedence `CLI overrides > config.toml > built-in defaults`.

Required or user-editable keys:

- `stock_ticker`
- `benchmark_ticker`
- `start_date`
- `end_date` or the literal string `today`
- `lump_sum_amount`
- `dca_monthly_amount`
- `output_dir`
- `output_format` (`csv` or `json`)

Validation rules:

- amounts must be strictly positive and finite
- ticker symbols must be nonempty strings
- start date must be before end date after resolving `today`
- output directory must be writable or creatable
- input dates are strict ISO `YYYY-MM-DD` strings

Output dates are stored as resolved calendar dates, not as the literal string `today`.

## Error Handling

- Fail fast on malformed config values.
- Surface network and Yahoo Finance errors clearly.
- Fail the run with exit code `4` if the two tickers do not have enough overlapping history.
- Return actionable messages instead of stack traces for expected user errors.
- Use stable exit codes for common failure modes:
  - `0` success
  - `2` config or validation failure
  - `3` network or data fetch failure
  - `4` insufficient overlapping history
- Print normal summaries to stdout and diagnostics/errors to stderr.
- Write result files atomically by writing to a temporary path and renaming into place.

## Testing Strategy

The first implementation slice should be driven by tests at three levels:

- Pure unit tests for metrics and date alignment helpers
- Simulation tests for lump-sum and DCA behavior on small synthetic series
- A light integration test for the CLI using a narrow data fixture or a mocked fetch layer

Because the MVP uses live data in normal runs, tests should not depend on the network for correctness.

## Output Contract

The machine-readable result file should be versioned and reproducible.

Canonical output values:

- `schema_version = "1.0"`
- `generated_at` is an ISO 8601 UTC timestamp
- date fields use `YYYY-MM-DD`
- `data_source = "yfinance"`
- `price_field = "adj_close"`
- `strategy` values are `lump_sum` and `dca`

Minimum fields:

- `schema_version`
- `generated_at`
- `ticker`
- `stock_ticker`
- `benchmark_ticker`
- `user_start_date`
- `user_end_date`
- `analysis_start`
- `analysis_end`
- `data_source`
- `price_field`
- `strategy`
- `investment_amount`
- `monthly_contribution`
- `total_contributions`
- `final_value`
- `cagr_pct`
- `xirr_pct`
- `total_return_pct`
- `annualized_volatility_pct`
- `max_drawdown_pct`
- `recovery_months`
- `multiple_on_invested`
- `warnings_json`
- `row_counts_json`

Record granularity:

- one row per `{ticker, strategy}` pair
- the emitted row set contains exactly four rows in the MVP: stock/lump_sum, stock/dca, benchmark/lump_sum, benchmark/dca
- JSON output is an array of the same flat records used by CSV
- Fields that do not apply to a given strategy are set to null rather than nested.

Metric applicability:

| Field | Lump Sum | DCA |
|---|---|---|
| `investment_amount` | populated | null |
| `monthly_contribution` | null | populated |
| `total_contributions` | equal to lump-sum amount | sum of all DCA contributions |
| `final_value` | populated | populated |
| `cagr_pct` | populated | null |
| `xirr_pct` | null | populated |
| `total_return_pct` | `final_value / investment_amount - 1` | `final_value / total_contributions - 1` |
| `annualized_volatility_pct` | populated | populated |
| `max_drawdown_pct` | populated | populated |
| `recovery_months` | populated | populated |
| `multiple_on_invested` | null | populated |
| `warnings_json` | JSON-encoded string of warning objects with `code` and `message` | same |
| `row_counts_json` | JSON-encoded string with `raw_stock_rows`, `raw_benchmark_rows`, `shared_rows`, `dca_contribution_rows` | same |

`row_counts_json` counts are defined as:

- `raw_stock_rows` and `raw_benchmark_rows`: source rows after timezone normalization and empty-row removal, before alignment
- `shared_rows`: rows in the final `[analysis_start, analysis_end]` intersection
- `dca_contribution_rows`: the number of DCA deposit dates emitted for the strategy

Numeric formatting:

- keep internal calculations in full floating-point precision
- round display values only at the reporting layer
- CSV exports should use stable decimal formatting for deterministic diffs

## Reproducibility

Each run should persist enough metadata to explain differences across time:

- fetch timestamp
- yfinance parameters
- chosen date range
- overlapping row counts
- final aligned start and end dates
- any warnings about gaps or skipped dates

## Output Naming

The result file should use a deterministic basename such as `wealth_analysis_{analysis_end:%Y%m%d}.{csv|json}` under `output_dir/reports/`.

- If the target file already exists, overwrite it atomically.
- Create parent directories if they do not exist.

## Repository Shape

Planned layout:

- `pyproject.toml`
- `README.md`
- `config.toml`
- `src/wealth_analyzer/`
- `tests/`
- `outputs/`

## Next Step

Write the implementation plan for the first MVP slice, then build the repo scaffold and code in small, test-first increments.

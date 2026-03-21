# LLM Implementation Checklist
## `wealth-accumulation-analyzer` — Step-by-Step Build Guide

> **For the implementing LLM:** Follow every step in order. Each step specifies exactly
> which file to create or edit, which source repo to reference, and which specific
> functions or patterns to adopt. Do not skip steps or reorder them.
> All source repos are read-only references — do not import them as packages unless
> explicitly told to. The goal is to understand their patterns and rewrite them
> cleanly for this project's architecture.

---

## Source Repositories (read before starting)

| Alias | URL | What to borrow |
|---|---|---|
| **quantstats** | https://github.com/ranaroussi/quantstats | Metrics engine — use as a direct dependency |
| **lumpsum_vs_dca** | https://github.com/Elucidation/lumpsum_vs_dca | DCA simulation logic, best/worst entry date tracking |
| **okama** | https://github.com/mbk-dev/okama | Benchmark comparison patterns, ETF-vs-stock chart style |
| **portfolio-backtester** | https://github.com/DmitryGubanov/portfolio-backtester | CLI output format, PERFORMANCE SUMMARY block, logging style |

---

## Phase 0 — Project Scaffold

### Step 0.1 — Create the repo skeleton

Create the following directory and file structure exactly. Every file listed here
will be populated in later steps. Create them as empty files for now except where
content is specified.

```
wealth-accumulation-analyzer/
├── pyproject.toml          ← populate in Step 0.2
├── config.toml             ← populate in Step 0.3
├── README.md               ← populate in Step 10.1
├── LICENSE                 ← use AGPL-3.0 text
├── .gitignore              ← populate in Step 0.4
├── src/
│   └── wealth_analyzer/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── data/
│       │   ├── __init__.py
│       │   ├── fetcher.py
│       │   └── cache.py
│       ├── analysis/
│       │   ├── __init__.py
│       │   ├── metrics.py
│       │   ├── lump_sum.py
│       │   └── dca.py
│       ├── charts/
│       │   ├── __init__.py
│       │   ├── style.py
│       │   ├── growth_curves.py
│       │   ├── drawdown_chart.py
│       │   ├── cagr_bar.py
│       │   ├── scatter.py
│       │   └── dca_vs_lump.py
│       └── reports/
│           ├── __init__.py
│           ├── excel_report.py
│           └── pdf_report.py
├── outputs/
│   ├── cache/
│   ├── charts/
│   ├── logs/
│   └── reports/
└── tests/
    ├── test_metrics.py
    ├── test_lump_sum.py
    ├── test_dca.py
    └── test_config.py
```

### Step 0.2 — Write `pyproject.toml`

```toml
[project]
name = "wealth-accumulation-analyzer"
version = "1.0.0"
description = "Long-term wealth accumulation: individual stocks vs ETF benchmarks"
requires-python = ">=3.11"
license = { text = "AGPL-3.0" }

dependencies = [
  "yfinance>=0.2.40",
  "pandas>=2.2",
  "numpy>=1.26",
  "scipy>=1.12",
  "matplotlib>=3.8",
  "quantstats>=0.0.62",
  "openpyxl>=3.1",
  "reportlab>=4.2",
  "pydantic>=2.6",
  "adjustText>=1.1",
  "rich>=13.7",
  "click>=8.1",
  "pyarrow>=15.0",
]

[project.scripts]
analyze      = "wealth_analyzer.cli:run_analysis"
fetch-data   = "wealth_analyzer.cli:run_fetch"
clear-cache  = "wealth_analyzer.cli:run_clear_cache"
list-tickers = "wealth_analyzer.cli:run_list_tickers"

[build-system]
requires      = ["hatchling"]
build-backend = "hatchling.build"

[tool.uv]
dev-dependencies = [
  "pytest>=8.1",
  "pytest-cov>=5.0",
  "ruff>=0.4",
  "mypy>=1.9",
]
```

After writing this file, run `uv sync` and confirm it resolves without errors.
Fix any version conflicts before continuing.

### Step 0.3 — Write `config.toml`

```toml
[general]
start_date     = "2013-01-01"
end_date       = "today"
cache_ttl_days = 1

[investment]
lump_sum_amount    = 10_000
dca_monthly_amount = 500
risk_free_rate     = 0.045

[tickers]
stocks = [
  "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN",
  "TSLA", "META", "JPM", "V", "ASML",
]
etfs = [
  "QQQM",
  "QQQ",
  "SMH",
  "SPY",
  "VTI",
]

# QQQM only has data from Oct 2020.
# For earlier dates, QQQ is used as the Nasdaq-100 proxy automatically.
qqqm_proxy = "QQQ"

[output]
output_dir      = "outputs"
chart_dpi       = 150
excel_filename  = "wealth_analysis_{date}.xlsx"
pdf_filename    = "wealth_analysis_{date}.pdf"
log_level       = "INFO"
```

### Step 0.4 — Write `.gitignore`

```
.venv/
__pycache__/
*.pyc
outputs/cache/
outputs/logs/
outputs/reports/
outputs/charts/
.DS_Store
*.egg-info/
dist/
```

---

## Phase 1 — Config Loader (`src/wealth_analyzer/config.py`)

**Reference:** No external repo needed. Write from scratch using `pydantic`.

Implement a `pydantic` `BaseSettings` model called `AppConfig` that:

1. Reads from `config.toml` using `tomllib` (Python 3.11 stdlib).
2. Has nested models: `GeneralConfig`, `InvestmentConfig`, `TickersConfig`, `OutputConfig`.
3. Validates that `start_date < end_date`. If `end_date == "today"`, resolve it to `datetime.date.today()` during validation.
4. Validates `lump_sum_amount > 0` and `dca_monthly_amount > 0`.
5. Validates `0.0 <= risk_free_rate <= 1.0`.
6. Exposes a module-level `load_config(path: str = "config.toml") -> AppConfig` function.

The function signature for `load_config` must be:

```python
def load_config(path: str = "config.toml") -> AppConfig:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    return AppConfig(**raw)
```

Write four unit tests in `tests/test_config.py`:
- Valid config loads without errors.
- `start_date >= end_date` raises `ValidationError`.
- Negative `lump_sum_amount` raises `ValidationError`.
- `end_date = "today"` resolves correctly to a `date` object.

---

## Phase 2 — Data Fetcher (`src/wealth_analyzer/data/fetcher.py`)

**Reference:** Pattern from **okama** — their `AssetList` class fetches a list of tickers
and returns them as a unified DataFrame. See: https://github.com/mbk-dev/okama
Look at `okama/_settings.py` and how `AssetList` stores per-ticker prices.
Do NOT use okama as a dependency — reimplement the pattern using `yfinance`.

### `fetcher.py` requirements:

1. Single public function: `fetch_prices(tickers: list[str], start: date, end: date) -> dict[str, pd.DataFrame]`
2. Always call `yfinance.download()` with `auto_adjust=True` (dividend-adjusted prices).
3. Batch all tickers in a single `yfinance.download()` call for efficiency.
4. If a ticker fails (empty DataFrame, all-NaN, or raises), log a `WARNING` and exclude it from the result — do not raise.
5. For the QQQM proxy rule: if `QQQM` is in the ticker list AND the start date is before `2020-10-13`, splice `QQQ` data before that date with `QQQM` data from that date onward. Normalize at the splice point so the series is continuous. Store the spliced series under the key `"QQQM"` in the output dict.
6. Each value in the returned dict is a `pd.DataFrame` with columns: `["Close", "Returns"]` where `Returns = log(Close / Close.shift(1))`.
7. Drop the first row of `Returns` (NaN from shift).

**Validate this function manually before continuing:**
```bash
uv run python -c "
from wealth_analyzer.data.fetcher import fetch_prices
from datetime import date
d = fetch_prices(['AAPL', 'SPY'], date(2015, 1, 1), date(2024, 12, 31))
print({k: len(v) for k, v in d.items()})
"
```
Expected output: both tickers present, each with ~2500 rows.

---

## Phase 3 — Cache Layer (`src/wealth_analyzer/data/cache.py`)

**Reference:** Pattern from **portfolio-backtester** — see how
https://github.com/DmitryGubanov/portfolio-backtester uses a `DataManager` class
to avoid re-downloading data on each run. Adapt the concept (not the code) to Parquet.

### `cache.py` requirements:

1. Three public functions:
   - `get(ticker: str, start: date, end: date) -> pd.DataFrame | None`
   - `set(ticker: str, start: date, end: date, df: pd.DataFrame) -> None`
   - `invalidate_all(cache_dir: str) -> int` — deletes all `.parquet` files, returns count deleted.
2. Cache key format: `{ticker}_{start.isoformat()}_{end.isoformat()}.parquet`
3. Cache path: `outputs/cache/` (read from `AppConfig.output.output_dir`).
4. `get()` returns `None` if the file does not exist OR if the file's mtime is older than `config.general.cache_ttl_days` days.
5. Use `pd.DataFrame.to_parquet()` and `pd.read_parquet()` with `pyarrow` engine.

---

## Phase 4 — Metrics Engine (`src/wealth_analyzer/analysis/metrics.py`)

**Reference:** Use **quantstats** as a direct dependency.
GitHub: https://github.com/ranaroussi/quantstats
Specific functions to call (do not reimplement):

```python
import quantstats as qs

# From a pd.Series of log returns:
qs.stats.cagr(returns)           # CAGR — use periods=252
qs.stats.sharpe(returns, rf=0.045)
qs.stats.sortino(returns, rf=0.045)
qs.stats.max_drawdown(returns)   # returns a negative float e.g. -0.42
qs.stats.drawdown_details(returns)   # DataFrame with start/end/recovery dates per drawdown
qs.stats.volatility(returns)     # annualized
```

**However**, you must wrap all quantstats calls in a single public function:

```python
def compute_metrics(
    returns: pd.Series,
    prices: pd.Series,
    risk_free_rate: float,
) -> dict[str, float | str | None]:
```

This wrapper returns a flat dict with these exact keys:
```
cagr, sharpe, sortino, max_drawdown_pct, max_drawdown_recovery_months,
annualized_volatility, total_return_pct, dividend_contribution_pct
```

For `max_drawdown_recovery_months`: call `qs.stats.drawdown_details(returns)`,
find the row with the largest drawdown, read its `"recovered"` date, compute months
between trough and recovery. If `"recovered"` is `NaT` (never recovered), return `None`.

For `dividend_contribution_pct`: this requires two price series — adj-close (total return)
and close (price only). `yfinance` with `auto_adjust=True` gives adj-close. To get
price-only close, call `yfinance.download(ticker, auto_adjust=False)["Close"]`.
Formula: `div_contribution = (adj_return / price_return) - 1` where both returns
are computed as `(final / initial) - 1`.

Also implement one standalone function NOT using quantstats:

```python
def xirr(cashflows: list[tuple[date, float]]) -> float:
```

This computes the internal rate of return for irregular cash flows (needed for DCA CAGR).
Use `scipy.optimize.brentq` on the NPV equation:
`NPV(r) = sum( cf / (1 + r)^((t - t0).days / 365) for t, cf in cashflows ) = 0`
Search for `r` in the interval `(-0.999, 100.0)`. Raise `ValueError` if no root found.

**Write tests in `tests/test_metrics.py`:**
- `xirr` on a known input: invest -$1000 on day 0, receive +$1100 exactly 1 year later → should return ~0.10 (10%).
- `compute_metrics` does not raise on a real ticker with 5+ years of data.

---

## Phase 5 — Lump Sum Analysis (`src/wealth_analyzer/analysis/lump_sum.py`)

**Reference:** Pattern from **okama** `AssetList` and `Portfolio` comparison examples.
See: https://github.com/mbk-dev/okama/blob/master/examples/03%20investment%20portfolios.ipynb
Study how okama aligns multiple assets to the same start date and normalizes to 1.0.
Also reference **portfolio-backtester**'s output format:
https://github.com/DmitryGubanov/portfolio-backtester
The `PERFORMANCE SUMMARY` block in that repo is the terminal output model.

### `lump_sum.py` requirements:

1. Single public function:
```python
def run_lump_sum(
    prices: dict[str, pd.DataFrame],
    config: AppConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
```
Returns:
- `results_df`: one row per (stock, etf_benchmark) pair with all metrics.
- `growth_df`: time-indexed DataFrame, one column per ticker showing portfolio value
  over time (starting from `lump_sum_amount`).

2. For each stock in `config.tickers.stocks`:
   a. For each ETF in `config.tickers.etfs`:
      - Find the **shared start date**: `max(stock_first_date, etf_first_date, config.general.start_date)`.
      - Slice both price series to `[shared_start : config.general.end_date]`.
      - Compute `growth_stock(t) = lump_sum_amount * (price_stock(t) / price_stock(t0))`.
      - Compute `growth_etf(t)` the same way.
      - Call `compute_metrics(returns_stock, prices_stock, config.investment.risk_free_rate)`.
      - Call `compute_metrics(returns_etf, prices_etf, config.investment.risk_free_rate)`.
      - Record a results row: all stock metrics, all ETF metrics, plus:
        - `outperformance_cagr_pp`: stock CAGR minus ETF CAGR in percentage points.
        - `outperformance_total_return_pp`: same for total return.
        - `shared_start_date`, `end_date`, `years_analyzed`.

3. `growth_df` columns: one column per unique ticker (stocks + ETFs), indexed by date,
   values = dollar portfolio value from `lump_sum_amount`. Align all columns to the
   **union** of dates, forward-fill for single missing days only.

4. Emit structured log output at `INFO` level after processing each stock, modeled on
   **portfolio-backtester**'s `PERFORMANCE SUMMARY` terminal block. Example:
```
══════════════════════════════════════
  NVDA  vs  SPY  |  2013-01-02 → 2025-03-01  (12.2 yrs)
  Lump Sum: $10,000
──────────────────────────────────────
  CAGR:        NVDA 42.1%  |  SPY 12.8%  (+29.3pp)
  Total Return: NVDA 8,432%  |  SPY 342%
  Sharpe:      NVDA 1.21   |  SPY 0.84
  Sortino:     NVDA 1.89   |  SPY 1.14
  Max DD:      NVDA -66.3% (recovered 18mo)  |  SPY -34.1% (recovered 6mo)
══════════════════════════════════════
```

Write one test in `tests/test_lump_sum.py`:
- Run with `["AAPL", "SPY"]` over a 5-year window. Confirm `results_df` has exactly 1 row,
  `growth_df` has 2 columns, final value > initial investment for SPY.

---

## Phase 6 — DCA Analysis (`src/wealth_analyzer/analysis/dca.py`)

**Reference:** This is the most important source.
Study **lumpsum_vs_dca** notebook carefully:
https://github.com/Elucidation/lumpsum_vs_dca/blob/master/Lumpsum_vs_DCA.ipynb

Key patterns to adopt from that notebook:
1. Monthly investment dates = first trading day of each month (use `pd.offsets.BMonthBegin()`).
2. Fractional shares: `shares_bought = monthly_amount / price_on_date`.
3. Cumulative shares: running total of `shares_bought`.
4. Portfolio value at time t: `cumulative_shares(t) * price(t)`.
5. Cost basis at time t: running total of all dollars invested through time t.
6. The difference chart (portfolio value minus cost basis) shows the unrealized gain over time.

Also adopt the **best/worst entry month logic** from that notebook:
```python
# From lumpsum_vs_dca notebook:
# lumpsum[:-1000].idxmax() → best entry date
# lumpsum[:-1000].idxmin() → worst entry date
```
Adapt this to find the best and worst single monthly DCA contribution by computing
the return on each individual monthly purchase independently.

### `dca.py` requirements:

1. Single public function:
```python
def run_dca(
    prices: dict[str, pd.DataFrame],
    config: AppConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
```
Returns:
- `results_df`: same schema as lump_sum results_df, plus extra columns:
  `best_entry_month`, `best_entry_return_pct`, `worst_entry_month`, `worst_entry_return_pct`,
  `avg_cost_per_share`, `current_price`, `total_contributions`.
- `growth_df`: time-indexed, one column per ticker = cumulative portfolio value.
- `cost_basis_df`: time-indexed, one column per ticker = cumulative cash invested.

2. Use `xirr` from `metrics.py` to compute DCA CAGR. Build cashflows as:
   `[(investment_date, -monthly_amount), ..., (end_date, +final_portfolio_value)]`
   Pass this list to `xirr()`.

3. Emit same structured log output as lump_sum.py with a `[DCA]` tag.

Write one test in `tests/test_dca.py`:
- Run with `["AAPL", "SPY"]` over a 5-year window. Confirm cumulative contributions
  equals `dca_monthly_amount * number_of_months` (within floating-point tolerance).

---

## Phase 7 — Charts (`src/wealth_analyzer/charts/`)

**Reference:** Chart style inspired by **okama**'s `plot_assets()` method.
See: https://github.com/mbk-dev/okama/blob/master/okama/plots.py
Key okama patterns to adopt:
- Log-scale Y axis for growth charts.
- ETF lines drawn as dashed/muted; stock lines as solid/bold.
- No gridlines (clean academic aesthetic — same as Network-Portfolio-v2).
- `adjustText` for non-overlapping scatter labels (okama maintainer confirmed this in
  GitHub Discussions: https://github.com/mbk-dev/okama/discussions/3).

### Step 7.1 — `style.py`

Define a shared style module. All chart modules import from here. Include:
- `STOCK_COLORS`: a list of 10+ distinct hex colors for stock lines.
- `ETF_COLORS`: a dict mapping `{"QQQM": "#...", "SMH": "#...", "SPY": "#...", "VTI": "#..."}`.
- `ETF_LINESTYLE`: `"--"` (dashed for ETFs).
- `STOCK_LINESTYLE`: `"-"` (solid for stocks).
- `FONT_BOLD`: `{"fontweight": "bold"}`.
- `DPI`: read from config at chart-generation time (default 150).
- `apply_clean_style(ax)`: a function that removes top/right spines, removes gridlines,
  sets label fonts to Arial/sans-serif. Match the aesthetic of Network-Portfolio-v2's plots.

### Step 7.2 — `growth_curves.py`

Function signature:
```python
def generate(
    growth_df: pd.DataFrame,         # from lump_sum.run_lump_sum or dca.run_dca
    cost_basis_df: pd.DataFrame | None,  # None for lump sum, provided for DCA
    config: AppConfig,
    output_dir: str,
    filename: str,
) -> Path:
```

Chart: one figure, one axis.
- Y axis: log scale. Label: `"Portfolio Value (USD, log scale)"`.
- X axis: date. Label: `"Date"`.
- For each ETF column: draw dashed line, ETF color, linewidth=1.5, alpha=0.7.
- For each stock column: draw solid line, stock color, linewidth=2.0, alpha=0.9.
- If `cost_basis_df` is provided (DCA mode): draw shaded area between cost basis and
  portfolio value for each ticker (use `ax.fill_between`), alpha=0.08.
- Horizontal dashed line at `lump_sum_amount` or initial cost basis.
- Legend outside right edge (to avoid overlap with lines).
- Apply `apply_clean_style(ax)`.
- Save to `output_dir/filename` at `config.output.chart_dpi` DPI.
- Return the `Path` of the saved file.

### Step 7.3 — `drawdown_chart.py`

Function signature:
```python
def generate(results_df: pd.DataFrame, config: AppConfig, output_dir: str) -> Path:
```

Chart: horizontal bar chart.
- One bar per ticker (stocks + ETFs), sorted ascending by max drawdown (worst at top).
- Bar color: red if `max_drawdown < -0.50`, orange if `< -0.30`, yellow-green otherwise.
- Annotate each bar with recovery time: e.g. `"18 mo"` or `"never"` if `None`.
- ETF bars: add a small `[ETF]` suffix to the label.
- X axis: percentage, range `[-1.0, 0.0]`. Format as `%`.
- Apply `apply_clean_style(ax)`.

### Step 7.4 — `cagr_bar.py`

Function signature:
```python
def generate(results_df: pd.DataFrame, config: AppConfig, output_dir: str) -> Path:
```

Chart: horizontal bar chart, one bar per stock, sorted descending by CAGR.
- Draw a vertical band (shaded rectangle using `ax.axvspan`) spanning the
  `[min_etf_cagr, max_etf_cagr]` range — this is the "ETF zone".
- Color each stock bar:
  - Green if CAGR > max ETF CAGR.
  - Red if CAGR < min ETF CAGR.
  - Yellow/orange if within the ETF range.
- Add vertical dashed lines for each individual ETF's CAGR, labeled with the ETF ticker.
- X axis: percentage. Title: `"CAGR (annualized) — Lump Sum"`.
- Apply `apply_clean_style(ax)`.

### Step 7.5 — `scatter.py`

Function signature:
```python
def generate(results_df: pd.DataFrame, config: AppConfig, output_dir: str) -> Path:
```

**Reference:** Directly inspired by **okama**'s `plot_assets()` scatter.
See the discussion about `adjustText` at:
https://github.com/mbk-dev/okama/discussions/3

Chart: scatter plot, X = annualized volatility, Y = CAGR.
- ETFs: filled squares (`marker="s"`), size=120, ETF color.
- Stocks: filled circles (`marker="o"`), size=80, stock color.
- Draw a diagonal reference line through the origin with slope =
  best ETF Sharpe ratio. Points above this line beat that ETF on risk-adjusted basis.
  Label this line `f"Sharpe = {best_sharpe:.2f} ({best_etf_ticker})"`.
- Use `adjustText` to prevent ticker label overlap:
  ```python
  from adjustText import adjust_text
  texts = [ax.text(vol, cagr, ticker) for ticker, vol, cagr in ...]
  adjust_text(texts, ax=ax)
  ```
- Apply `apply_clean_style(ax)`.

### Step 7.6 — `dca_vs_lump.py`

Function signature:
```python
def generate(
    lump_results: pd.DataFrame,
    dca_results: pd.DataFrame,
    config: AppConfig,
    output_dir: str,
) -> Path:
```

Chart: grouped bar chart.
- For each ticker: two bars side-by-side — lump sum final value (blue) and DCA final
  value (orange).
- Add a horizontal line at `lump_sum_amount` (initial investment reference).
- X axis: ticker names. Y axis: `"Final Portfolio Value (USD)"`.
- Add value labels on top of each bar formatted as `"$XX,XXX"`.
- Apply `apply_clean_style(ax)`.

---

## Phase 8 — Excel Report (`src/wealth_analyzer/reports/excel_report.py`)

**Reference:** No specific source repo — write from scratch with `openpyxl`.

Function signature:
```python
def build_excel(
    lump_results: pd.DataFrame,
    dca_results: pd.DataFrame,
    lump_growth: pd.DataFrame,
    dca_growth: pd.DataFrame,
    dca_cost_basis: pd.DataFrame,
    config: AppConfig,
    output_dir: str,
) -> Path:
```

### Tab 1: `Summary`
- Write `lump_results` as a table, one row per stock (use the row where
  `benchmark == "SPY"` for each stock to avoid duplicates).
- Columns: `Ticker | CAGR (%) | Total Return (%) | Final Value ($) | Max DD (%) |
  Recovery (mo) | Sharpe | Sortino | Ann. Vol (%) | Div Contribution (%) |
  vs SPY (pp) | vs QQQM (pp)`.
- Sort by CAGR descending.
- Apply conditional formatting to CAGR column:
  - Green fill if CAGR > SPY CAGR (pull from ETF rows of `lump_results`).
  - Red fill if CAGR < worst ETF CAGR.
  - Yellow fill otherwise.
- Freeze top row (header) and first column (ticker).

### Tab 2: `Lump Sum Detail`
- Write `lump_growth` transposed (dates as rows, tickers as columns).
- Format all values as `"$#,##0.00"`.

### Tab 3: `DCA Detail`
- Write `dca_growth` and `dca_cost_basis` side by side, separated by an empty column.
- Section headers in row 1: `"DCA Portfolio Value"` and `"Cumulative Cost Basis"`.
- Format as `"$#,##0.00"`.

### Tab 4: `ETF Benchmarks`
- Write ETF rows from `lump_results` as a table. Same columns as Summary tab.
- No conditional formatting needed.

### Tab 5: `Metric Definitions`
- Write a two-column table: `Metric | Definition`.
- Include plain-language definitions for every metric.
- Mark the `quantstats` source for metrics that come from that library:
  e.g. `"Sharpe Ratio — Annualized risk-adjusted return (source: quantstats)"`.

### Formatting rules for all tabs:
- Font: Calibri 11pt for data, Calibri 12pt bold for headers.
- Header row: blue fill (`"1F4E79"`), white text.
- Alternating row shading: light gray (`"F2F2F2"`) every other row.
- Column widths: auto-fit to content.
- Return the output `Path`.

---

## Phase 9 — PDF Report (`src/wealth_analyzer/reports/pdf_report.py`)

**Reference:** Use `reportlab` for layout. No external repo pattern needed.

Function signature:
```python
def build_pdf(
    lump_results: pd.DataFrame,
    dca_results: pd.DataFrame,
    chart_paths: dict[str, Path],
    config: AppConfig,
    output_dir: str,
) -> Path:
```

`chart_paths` is a dict keyed by chart name:
`{"growth_lump", "growth_dca", "cagr_bar", "drawdown", "scatter", "dca_vs_lump"}`

### PDF structure (in order):

1. **Cover page**
   - Title: `"Long-Term Wealth Accumulation Analysis"`
   - Subtitle: `f"{config.general.start_date} → {config.general.end_date}"`
   - Line: `f"Lump Sum: ${config.investment.lump_sum_amount:,} | DCA: ${config.investment.dca_monthly_amount:,}/month"`
   - Line: `f"Benchmarks: {', '.join(config.tickers.etfs)}"`
   - Line: `"Data source: Yahoo Finance (dividend-adjusted)"`
   - Date generated.

2. **Executive Summary** (auto-generated narrative, 3–5 sentences)
   Compute these facts from `lump_results` and write them as a paragraph:
   - Number of stocks that beat all ETFs on CAGR (lump sum).
   - Number that underperformed all ETFs.
   - The single best-performing stock (CAGR) and its outperformance vs SPY in pp.
   - The single worst-performing stock.
   - Whether lump sum or DCA produced better results more often overall.
   Example: *"Of the 10 stocks analyzed, 4 outperformed all ETF benchmarks on a CAGR basis
   under the lump-sum strategy. NVDA was the standout performer, delivering a CAGR 29.3pp
   above SPY over 12.2 years..."*

3. **Lump Sum Results Table** — embed the Summary tab data as a formatted reportlab table.

4. **DCA Results Table** — same format, DCA metrics.

5. **Charts** — embed all 6 PNG files at full page width, one per page, with a caption below.
   Caption format: `"Figure N: {chart_title}"`.

6. **Methodology Notes** — one paragraph explaining:
   - Yahoo Finance `auto_adjust=True` for total return.
   - XIRR used for DCA CAGR.
   - Risk-free rate used.
   - QQQM proxy rule.

7. **Disclaimer** — standard educational-use disclaimer, italicized, small font.

---

## Phase 10 — CLI Orchestrator (`src/wealth_analyzer/cli.py`)

**Reference:** Terminal output style from **portfolio-backtester**.
See: https://github.com/DmitryGubanov/portfolio-backtester
Study the `####### PERFORMANCE SUMMARY #######` terminal block in `folio.py`.
Adapt it using `rich` instead of plain print statements.

### Functions to implement:

```python
import click
from rich.console import Console
from rich.table import Table

@click.group()
def cli(): pass

@cli.command()
@click.option("--config", default="config.toml")
@click.option("--start", default=None)
@click.option("--lump-sum", default=None, type=float)
@click.option("--dca-monthly", default=None, type=float)
@click.option("--strategy", default="both", type=click.Choice(["lump-sum", "dca", "both"]))
@click.option("--no-cache", is_flag=True)
@click.option("--no-pdf", is_flag=True)
@click.option("--dry-run", is_flag=True)
def run_analysis(...): ...

@cli.command()
def run_fetch(): ...

@cli.command()
def run_clear_cache(): ...

@cli.command()
def run_list_tickers(): ...
```

### `run_analysis` pipeline (in order):
1. Load config. Apply any CLI flag overrides.
2. Set up logging: `logging.basicConfig` to both file (`outputs/logs/analysis_{ts}.log`)
   and stdout at the configured level.
3. Print a `rich` startup banner:
   ```
   ╔══════════════════════════════════════════╗
   ║   Wealth Accumulation Analyzer v1.0.0   ║
   ╚══════════════════════════════════════════╝
   Tickers: AAPL, MSFT, NVDA, ...
   Benchmarks: QQQM, SMH, SPY, VTI
   Period: 2013-01-01 → 2025-03-21 (12.2 years)
   Strategy: Lump Sum ($10,000) + DCA ($500/mo)
   ```
4. Fetch data (check cache first, fall back to yfinance).
5. Run `lump_sum.run_lump_sum()` if strategy is `"lump-sum"` or `"both"`.
6. Run `dca.run_dca()` if strategy is `"dca"` or `"both"`.
7. Generate all charts (call all 6 chart `generate()` functions).
8. Build Excel report.
9. Build PDF report (unless `--no-pdf`).
10. Print final `rich` summary table to terminal showing top 5 and bottom 5 stocks by CAGR.
11. Print output file paths.
12. If `--dry-run`: skip steps 8–11 and only print the summary table to terminal.

### Terminal Summary Table (using `rich.table.Table`):
```
┌────────┬──────────┬──────────┬──────────┬───────────┬──────────────┐
│ Ticker │ CAGR     │ vs SPY   │ Sharpe   │ Max DD    │ Final Value  │
├────────┼──────────┼──────────┼──────────┼───────────┼──────────────┤
│ NVDA   │ 42.1%  ↑ │ +29.3pp  │ 1.21     │ -66.3%    │ $893,200     │
│ AAPL   │ 25.3%  ↑ │ +12.5pp  │ 1.05     │ -44.1%    │ $182,400     │
│ ...    │          │          │          │           │              │
├────────┼──────────┼──────────┼──────────┼───────────┼──────────────┤
│ SPY    │ 12.8%    │ (bench)  │ 0.84     │ -34.1%    │ $47,200      │
│ QQQM   │ 17.1%    │ (bench)  │ 0.92     │ -32.6%    │ $70,400      │
└────────┴──────────┴──────────┴──────────┴───────────┴──────────────┘
```
Use green text for stocks beating SPY CAGR, red for underperforming.

---

## Phase 11 — README (`README.md`)

Write the full README using the structure from **Network-Portfolio-v2** as a template
for formatting quality, but with completely original content.

Required sections (in order):
1. Badges: Python 3.11+, uv, License AGPL-3.0
2. Project Overview (3–4 sentences)
3. Sample Output Images (leave placeholder paths — actual images generated on first run)
4. Table of Contents
5. Key Features (match the plan document sections)
6. Repo Structure (copy from plan — keep the annotated tree)
7. Installation (uv) — verbatim from plan, Step 0.2 expanded
8. Configuration (`config.toml` — annotated)
9. Usage Guide (all CLI commands with examples)
10. Methodology (Data Pipeline, Lump Sum, DCA, Metrics Table)
11. Output: Excel Report (tab descriptions)
12. Output: PDF Report (page structure)
13. Output: PNG Charts (all 6, with descriptions)
14. Source References (the 4 GitHub repos listed above, with one sentence on what was adopted from each)
15. Assumptions & Limitations
16. Future Enhancements
17. License & Disclaimer

---

## Phase 12 — Final Validation

Run these commands in order. Each must pass cleanly before the project is considered complete.

```bash
# 1. Dependency install
uv sync

# 2. Unit tests
uv run pytest tests/ -v --tb=short

# 3. Full analysis dry run (no files written, just terminal output)
uv run analyze --dry-run

# 4. Full analysis run (writes all outputs)
uv run analyze

# 5. Verify outputs exist
ls outputs/reports/
ls outputs/charts/

# 6. Type check
uv run mypy src/ --ignore-missing-imports

# 7. Lint
uv run ruff check src/
```

Expected output from step 4 (terminal, abbreviated):
```
╔══════════════════════════════════════════╗
║   Wealth Accumulation Analyzer v1.0.0   ║
╚══════════════════════════════════════════╝
...
✓ Data fetched: 14 tickers (10 stocks + 4 ETFs)
✓ Lump sum analysis complete: 10 stocks × 4 benchmarks = 40 comparisons
✓ DCA analysis complete: 40 comparisons
✓ Charts generated: 6 files
✓ Excel report: outputs/reports/wealth_analysis_20250321.xlsx
✓ PDF report:   outputs/reports/wealth_analysis_20250321.pdf

[Summary Table here]
```

---

## Appendix — Common Pitfalls to Avoid

| Problem | Root Cause | Fix |
|---|---|---|
| `quantstats.stats.cagr` returns wrong value | quantstats had a CAGR bug where years used calendar days not trading periods — fixed in recent versions | Ensure `quantstats>=0.0.62` in `pyproject.toml` |
| `QQQM` returns empty DataFrame before Oct 2020 | Ticker didn't exist | Implement the QQQ proxy splice in `fetcher.py` Step 2 |
| `xirr` doesn't converge | Cashflow signs wrong (all positive or all negative) | Ensure initial investments are negative and final value is positive |
| `adjustText` labels still overlap on scatter | Too many tickers, default iterations insufficient | Pass `force_text=(0.5, 1.0)` and `expand_text=(1.2, 1.4)` to `adjust_text()` |
| Excel conditional formatting breaks on open | `openpyxl` ColorScale rules require explicit min/mid/max | Use `Rule(type='colorScale', colorScale=ColorScale(...))` not shorthand |
| `reportlab` images blurry in PDF | Default image scaling | Pass `width=doc.width, height=doc.width * (img_h/img_w)` to preserve aspect ratio |
| DCA cost basis doesn't match expected | Off-by-one on monthly dates | Use `pd.date_range(start, end, freq='BMS')` (Business Month Start) not `MS` |

---

*Checklist generated March 2026 for `wealth-accumulation-analyzer` v1.0.0*

# Wealth Accumulation Analyzer Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents are available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-ready Python CLI that compares stocks vs ETF benchmarks using live market data, quantstats-backed metrics, DCA simulation, charts, Excel/PDF reports, caching, and polished terminal output.

**Architecture:** Use a small `src/wealth_analyzer/` package with clear boundaries: config parsing, data fetch/cache, metrics, analysis, charts, reports, and CLI orchestration. Keep external dependencies behind narrow interfaces so tests can swap in fixtures and synthetic series. The CLI stays thin; all business logic lives in modules that can be unit-tested independently.

**Tech Stack:** Python 3.11, `uv`, `click`, `pydantic`, `tomllib`, `yfinance`, `pandas`, `numpy`, `scipy`, `quantstats`, `matplotlib`, `adjustText`, `openpyxl`, `reportlab`, `rich`, `pyarrow`, `pytest`, `ruff`, `mypy`.

---

## Chunk 1: Project scaffold and packaging

**Files:**
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/pyproject.toml`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/config.toml`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/LICENSE`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/__init__.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/cli.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/config.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/data/__init__.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/data/fetcher.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/data/cache.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/analysis/__init__.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/analysis/metrics.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/analysis/lump_sum.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/analysis/dca.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/charts/__init__.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/charts/style.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/charts/growth_curves.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/charts/drawdown_chart.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/charts/cagr_bar.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/charts/scatter.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/charts/dca_vs_lump.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/reports/__init__.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/reports/excel_report.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/reports/pdf_report.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/tests/test_config.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/tests/test_metrics.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/tests/test_lump_sum.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/tests/test_dca.py`
- Create: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/.gitignore`

- [ ] **Step 1: Write the empty package scaffold and dependency manifest**

```bash
uv sync
```

Expected: dependency resolution succeeds once the initial package files exist.

- [ ] **Step 2: Add import smoke tests for the package layout**

```python
def test_package_imports():
    import wealth_analyzer
    import wealth_analyzer.config
    import wealth_analyzer.data.fetcher
```

- [ ] **Step 3: Run the smoke test and confirm it fails before implementation**

```bash
uv run pytest tests/test_imports.py -v
```

Expected: fail on missing modules or symbols.

- [ ] **Step 4: Implement the minimal package exports**

```python
# src/wealth_analyzer/__init__.py
__version__ = "1.0.0"
```

- [ ] **Step 5: Re-run the smoke test and confirm it passes**

```bash
uv run pytest tests/test_imports.py -v
```

- [ ] **Step 6: Commit the scaffold**

```bash
git add pyproject.toml config.toml LICENSE src tests .gitignore
git commit -m "chore: add project scaffold"
```

---

## Chunk 2: Config loader and runtime settings

**Files:**
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/config.py`
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/tests/test_config.py`
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/config.toml`

- [ ] **Step 1: Write failing config tests**

Cover valid config load, `start_date >= end_date`, negative investment amounts, and `today` resolution.

- [ ] **Step 2: Run the config tests and confirm they fail**

```bash
uv run pytest tests/test_config.py -v
```

- [ ] **Step 3: Implement nested `pydantic` models and `load_config()`**

Use strict ISO date parsing, resolve `today`, and enforce `CLI > config > defaults` precedence.

- [ ] **Step 4: Re-run the config tests until green**

```bash
uv run pytest tests/test_config.py -v
```

- [ ] **Step 5: Commit the config layer**

```bash
git add src/wealth_analyzer/config.py tests/test_config.py config.toml
git commit -m "feat: add config loader"
```

---

## Chunk 3: Live data fetcher and cache

**Files:**
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/data/fetcher.py`
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/data/cache.py`
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/tests/test_fetcher.py`
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/tests/test_cache.py`

Borrow the batch-fetch pattern and date alignment approach from `okama`, but reimplement it directly with `yfinance`.

- [ ] **Step 1: Write failing fetch/cache tests**

Mock `yfinance.download`, verify batched fetch behavior, QQQM splice handling, cache TTL invalidation, and Parquet read/write.

- [ ] **Step 2: Run the tests and confirm they fail**

```bash
uv run pytest tests/test_fetcher.py tests/test_cache.py -v
```

- [ ] **Step 3: Implement `fetch_prices()` and cache helpers**

Return per-ticker DataFrames with `Close` and `Returns`, handle failures by logging warnings, and implement the QQQM proxy splice.

- [ ] **Step 4: Re-run the fetch/cache tests until green**

```bash
uv run pytest tests/test_fetcher.py tests/test_cache.py -v
```

- [ ] **Step 5: Commit the data layer**

```bash
git add src/wealth_analyzer/data tests/test_fetcher.py tests/test_cache.py
git commit -m "feat: add data fetch and cache"
```

---

## Chunk 4: Metrics engine

**Files:**
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/analysis/metrics.py`
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/tests/test_metrics.py`

Use `quantstats` as a direct dependency. Wrap its API in one public `compute_metrics()` function and keep `xirr()` separate.

- [ ] **Step 1: Write failing tests for `xirr()` and `compute_metrics()`**

Cover a known 10% IRR case and a real ticker series with 5+ years of data.

- [ ] **Step 2: Run the metrics tests and confirm they fail**

```bash
uv run pytest tests/test_metrics.py -v
```

- [ ] **Step 3: Implement `xirr()` with `scipy.optimize.brentq`**

Use the sign convention and NPV equation from the checklist. Raise `ValueError` on no root.

- [ ] **Step 4: Implement `compute_metrics()` via quantstats**

Return the flat dict with the exact required keys: CAGR, Sharpe, Sortino, max drawdown, recovery months, annualized volatility, total return, dividend contribution.

- [ ] **Step 5: Re-run the metrics tests until green**

```bash
uv run pytest tests/test_metrics.py -v
```

- [ ] **Step 6: Commit the metrics engine**

```bash
git add src/wealth_analyzer/analysis/metrics.py tests/test_metrics.py
git commit -m "feat: add metrics engine"
```

---

## Chunk 5: Lump-sum and DCA simulations

**Files:**
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/analysis/lump_sum.py`
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/analysis/dca.py`
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/tests/test_lump_sum.py`
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/tests/test_dca.py`

Borrow DCA logic, monthly purchase timing, and best/worst entry month tracking from `lumpsum_vs_dca`. Borrow comparison and date-alignment patterns from `okama`. Borrow the terminal summary style from `portfolio-backtester`.

- [ ] **Step 1: Write failing simulation tests**

Verify one-row lump-sum output for a single stock/ETF pair and DCA contribution totals over a 5-year window.

- [ ] **Step 2: Run simulation tests and confirm they fail**

```bash
uv run pytest tests/test_lump_sum.py tests/test_dca.py -v
```

- [ ] **Step 3: Implement `run_lump_sum()`**

Align to `analysis_start`, compute growth curves, compute metrics, and emit the structured performance summary block.

- [ ] **Step 4: Implement `run_dca()`**

Build monthly cashflows, cumulative shares, cost basis, XIRR CAGR, best/worst entry month stats, and DCA summary logging.

- [ ] **Step 5: Re-run simulation tests until green**

```bash
uv run pytest tests/test_lump_sum.py tests/test_dca.py -v
```

- [ ] **Step 6: Commit the analysis modules**

```bash
git add src/wealth_analyzer/analysis tests/test_lump_sum.py tests/test_dca.py
git commit -m "feat: add lump sum and dca analysis"
```

---

## Chunk 6: Charts and shared styling

**Files:**
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/charts/style.py`
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/charts/growth_curves.py`
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/charts/drawdown_chart.py`
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/charts/cagr_bar.py`
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/charts/scatter.py`
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/charts/dca_vs_lump.py`

Borrow the chart language from `okama`: log-scale growth curves, ETF dashed lines, `adjustText` scatter labels, and clean academic styling.

- [ ] **Step 1: Write chart smoke tests or generation checks**

Use a small synthetic DataFrame to confirm every chart function writes a PNG and returns a `Path`.

- [ ] **Step 2: Run the chart checks and confirm they fail**

```bash
uv run pytest tests/test_charts.py -v
```

- [ ] **Step 3: Implement the shared style module**

Standardize colors, line styles, DPI, fonts, and axis cleanup in one place.

- [ ] **Step 4: Implement each chart generator**

Add the growth curve, drawdown, CAGR bar, scatter, and DCA vs lump-sum visuals with the exact labels and styles from the checklist.

- [ ] **Step 5: Re-run the chart checks until green**

```bash
uv run pytest tests/test_charts.py -v
```

- [ ] **Step 6: Commit the chart layer**

```bash
git add src/wealth_analyzer/charts tests/test_charts.py
git commit -m "feat: add chart generation"
```

---

## Chunk 7: Excel and PDF reports

**Files:**
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/reports/excel_report.py`
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/reports/pdf_report.py`
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/tests/test_reports.py`

- [ ] **Step 1: Write report tests**

Check workbook creation, sheet names, a few anchor cells, and that the PDF file is created with embedded charts.

- [ ] **Step 2: Run the report tests and confirm they fail**

```bash
uv run pytest tests/test_reports.py -v
```

- [ ] **Step 3: Implement the Excel writer with `openpyxl`**

Create the Summary, Lump Sum Detail, DCA Detail, ETF Benchmarks, and Metric Definitions sheets with formatting and conditional fills.

- [ ] **Step 4: Implement the PDF renderer with `reportlab`**

Generate cover, summary narrative, tables, charts, methodology, and disclaimer pages in the required order.

- [ ] **Step 5: Re-run the report tests until green**

```bash
uv run pytest tests/test_reports.py -v
```

- [ ] **Step 6: Commit the reporting layer**

```bash
git add src/wealth_analyzer/reports tests/test_reports.py
git commit -m "feat: add excel and pdf reports"
```

---

## Chunk 8: CLI orchestrator and terminal UX

**Files:**
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/src/wealth_analyzer/cli.py`
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/tests/test_cli.py`

Borrow the terminal output structure and performance summary style from `portfolio-backtester`, but implement it with `rich`.

- [ ] **Step 1: Write CLI tests**

Check argument parsing, config overrides, `--dry-run`, `--no-cache`, `--no-pdf`, and the main summary table layout.

- [ ] **Step 2: Run the CLI tests and confirm they fail**

```bash
uv run pytest tests/test_cli.py -v
```

- [ ] **Step 3: Implement the `click` command group and subcommands**

Wire `run_analysis`, `run_fetch`, `run_clear_cache`, and `run_list_tickers`.

- [ ] **Step 4: Add logging, startup banner, and final summary output**

Write to both stdout and the timestamped log file, and ensure the summary table matches the checklist’s shape.

- [ ] **Step 5: Re-run the CLI tests until green**

```bash
uv run pytest tests/test_cli.py -v
```

- [ ] **Step 6: Commit the CLI**

```bash
git add src/wealth_analyzer/cli.py tests/test_cli.py
git commit -m "feat: add cli orchestrator"
```

---

## Chunk 9: README, docs, and source references

**Files:**
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/README.md`
- Modify: `/Users/edis-mac/Documents/03-Eddie-Python-Projects/python/wealth-accumulation-analyzer/docs/superpowers/specs/IMPLEMENTATION_CHECKLIST.md` only if the checklist itself needs an erratum note

Write the README in the structure requested by the checklist, with the annotated tree, installation steps, source references, and output sections.

- [ ] **Step 1: Draft the README against the finished codebase**

Ensure every CLI command, report type, and chart is documented with the actual filenames and outputs.

- [ ] **Step 2: Sanity-check links and commands**

Verify that commands use `uv run`, references are current, and the source repo adoption notes are specific and non-overlapping.

- [ ] **Step 3: Commit the documentation update**

```bash
git add README.md
git commit -m "docs: update readme"
```

---

## Chunk 10: Full validation and release hardening

**Files:**
- Modify only if required by validation failures

- [ ] **Step 1: Run dependency resolution**

```bash
uv sync
```

- [ ] **Step 2: Run the full test suite**

```bash
uv run pytest tests/ -v --tb=short
```

- [ ] **Step 3: Run a dry-run analysis**

```bash
uv run analyze --dry-run
```

- [ ] **Step 4: Run the full analysis**

```bash
uv run analyze
```

- [ ] **Step 5: Verify outputs exist**

```bash
ls outputs/reports/
ls outputs/charts/
```

- [ ] **Step 6: Type-check and lint**

```bash
uv run mypy src/ --ignore-missing-imports
uv run ruff check src/
```

- [ ] **Step 7: Fix validation failures and rerun until clean**

Resolve issues in the smallest possible scope; do not widen the change set unnecessarily.

- [ ] **Step 8: Commit the final state**

```bash
git add .
git commit -m "feat: ship wealth accumulation analyzer"
```

---

## Implementation Notes

- `quantstats` is the metrics source of truth. Do not reimplement Sharpe, Sortino, drawdown details, or volatility unless a test proves a mismatch.
- `lumpsum_vs_dca` is the source for monthly contribution logic, fractional share accumulation, and best/worst entry month tracking.
- `okama` informs date-alignment behavior and the visual language for growth/scatter charts, but its code is not copied.
- `portfolio-backtester` informs the CLI banner, performance summary block, and logging style.
- Guard against silent finance bugs:
  - XIRR sign convention must be negative contributions and positive liquidation value.
  - QQQM needs the proxy splice before 2020-10-13.
  - Keep adjusted-close and price-only series separate when computing dividend contribution.
  - Use the shared calendar consistently when aligning stock/ETF comparisons.
- Prefer small, verified commits after each chunk. If a chunk touches multiple disjoint modules, split it further before coding.


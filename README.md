[![AI Slop Inside](https://sladge.net/badge.svg)](https://sladge.net)

# Wealth Accumulation Analyzer

Compare long-term wealth accumulation for individual stocks versus benchmark ETFs using live historical market data.

This repository is being built as a production-ready Python CLI, starting with a single-ticker end-to-end MVP:

- Fetch live dividend-adjusted price data from Yahoo Finance via `yfinance`
- Simulate lump-sum and monthly DCA investing
- Compute core performance metrics
- Emit a terminal summary and machine-readable output

## Current Scope

The first implementation slice focuses on one stock versus one benchmark so the full pipeline can be proven before expanding to multi-ticker comparison reports.

## Planned Structure

- `src/wealth_analyzer/config.py` - config parsing and validation
- `src/wealth_analyzer/data/` - live price fetch and normalization
- `src/wealth_analyzer/analysis/` - lump-sum, DCA, and metrics logic
- `src/wealth_analyzer/reports/` - terminal and file outputs
- `tests/` - unit and integration coverage

## Status

This repo currently contains the scaffold and design documentation. Implementation will follow the approved plan.

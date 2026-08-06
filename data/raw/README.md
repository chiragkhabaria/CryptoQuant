# Raw Data

This directory stores raw, unprocessed market data collected from external sources.

## Purpose

- Historical price data from Coinbase API
- Raw order book snapshots
- Trade tick data
- Market depth data
- Raw market indicators from external sources

## Guidelines

- Data in this directory should never be modified after collection
- Use timestamped filenames for versioning
- Organize by asset and date (e.g., `BTC-USD/2026-08/prices.parquet`)
- Raw data serves as the source of truth for all downstream processing

## Format

Prefer Parquet format for efficiency:
- Columnar storage
- Efficient compression
- Fast query performance
- Schema preservation

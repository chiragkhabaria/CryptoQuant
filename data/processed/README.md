# Processed Data

This directory contains cleaned, transformed, and feature-engineered data ready for analysis and modeling.

## Purpose

- Cleaned and normalized price data
- Calculated technical indicators
- Feature matrices for backtesting
- Aggregated market statistics
- Prepared datasets for strategy evaluation

## Guidelines

- All data should be reproducible from raw data + processing scripts
- Document transformations applied
- Include metadata files describing schema and lineage
- Use consistent naming conventions
- Version processed datasets

## Format

Use Parquet or CSV depending on use case:
- **Parquet**: For large datasets, time-series data
- **CSV**: For smaller datasets, human-readable exports

## Lineage

Each processed dataset should maintain a reference to:
- Source raw data files
- Processing script version
- Timestamp of processing
- Data quality metrics

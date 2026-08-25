/*
Market Prices Ingestion Validation - Simplified

Purpose:
- Quick count of candles by currency pair
- Identify missing hourly records and gaps
- Simple summary for re-ingestion decisions

This script is read-only and intended for Azure SQL / SQL Server.
*/

SET NOCOUNT ON;

PRINT '============================================================';
PRINT 'Market Prices Ingestion Summary';
PRINT '============================================================';
PRINT '';

-- ============================================================
-- 1. Overall Summary
-- ============================================================
PRINT '1) Overall Summary';

IF OBJECT_ID('crypto.market_prices', 'U') IS NOT NULL
BEGIN
    SELECT
        COUNT(*) AS total_candles,
        COUNT(DISTINCT trading_pair_id) AS distinct_pairs,
        MIN(timestamp) AS first_candle_utc,
        MAX(timestamp) AS latest_candle_utc,
        DATEDIFF(DAY, MIN(timestamp), MAX(timestamp)) AS days_span
    FROM crypto.market_prices;
END
ELSE
BEGIN
    PRINT 'ERROR: crypto.market_prices table not found';
END;

PRINT '';
PRINT '============================================================';

-- ============================================================
-- 2. Count and Coverage by Currency Pair
-- ============================================================
PRINT '2) Count and Coverage by Currency Pair';

IF OBJECT_ID('crypto.market_prices', 'U') IS NOT NULL
   AND OBJECT_ID('crypto.trading_pairs', 'U') IS NOT NULL
BEGIN
    SELECT
        tp.symbol AS currency_pair,
        COUNT(*) AS actual_candles,
        MIN(mp.timestamp) AS first_candle,
        MAX(mp.timestamp) AS last_candle,
        DATEDIFF(HOUR, MIN(mp.timestamp), MAX(mp.timestamp)) + 1 AS expected_candles,
        DATEDIFF(HOUR, MIN(mp.timestamp), MAX(mp.timestamp)) + 1 - COUNT(*) AS missing_candles,
        CAST(COUNT(*) * 100.0 / NULLIF(DATEDIFF(HOUR, MIN(mp.timestamp), MAX(mp.timestamp)) + 1, 0) AS DECIMAL(5,2)) AS coverage_percent,
        DATEDIFF(HOUR, MAX(mp.timestamp), SYSUTCDATETIME()) AS hours_since_latest
    FROM crypto.market_prices AS mp
    INNER JOIN crypto.trading_pairs AS tp
        ON tp.id = mp.trading_pair_id
    GROUP BY tp.symbol
    ORDER BY coverage_percent ASC, tp.symbol;
END
ELSE
BEGIN
    PRINT 'ERROR: Required tables not found';
END;

PRINT '';
PRINT '============================================================';

-- ============================================================
-- 3. Gap Summary (Gaps > 1 hour)
-- ============================================================
PRINT '3) Gap Summary by Currency Pair';

IF OBJECT_ID('crypto.market_prices', 'U') IS NOT NULL
   AND OBJECT_ID('crypto.trading_pairs', 'U') IS NOT NULL
BEGIN
    WITH ordered_candles AS (
        SELECT
            mp.trading_pair_id,
            tp.symbol,
            mp.timestamp,
            LEAD(mp.timestamp) OVER (
                PARTITION BY mp.trading_pair_id
                ORDER BY mp.timestamp
            ) AS next_timestamp
        FROM crypto.market_prices AS mp
        INNER JOIN crypto.trading_pairs AS tp
            ON tp.id = mp.trading_pair_id
    ),
    gaps AS (
        SELECT
            symbol,
            DATEDIFF(HOUR, timestamp, next_timestamp) AS hours_gap
        FROM ordered_candles
        WHERE next_timestamp IS NOT NULL
          AND DATEDIFF(HOUR, timestamp, next_timestamp) > 1
    )
    SELECT
        symbol AS currency_pair,
        COUNT(*) AS gap_count,
        SUM(hours_gap) AS total_hours_missing,
        MIN(hours_gap) AS min_gap_hours,
        MAX(hours_gap) AS max_gap_hours,
        AVG(hours_gap) AS avg_gap_hours
    FROM gaps
    GROUP BY symbol
    ORDER BY total_hours_missing DESC, symbol;
    
    IF @@ROWCOUNT = 0
    BEGIN
        PRINT 'No gaps detected - all hourly records present!';
    END;
END
ELSE
BEGIN
    PRINT 'ERROR: Required tables not found';
END;

PRINT '';
PRINT '============================================================';

-- ============================================================
-- 4. Re-Ingestion Recommendations
-- ============================================================
PRINT '4) Re-Ingestion Recommendations';

IF OBJECT_ID('crypto.market_prices', 'U') IS NOT NULL
   AND OBJECT_ID('crypto.trading_pairs', 'U') IS NOT NULL
BEGIN
    WITH coverage AS (
        SELECT
            tp.symbol AS currency_pair,
            COUNT(*) AS actual_candles,
            MIN(mp.timestamp) AS first_candle,
            DATEDIFF(HOUR, MIN(mp.timestamp), MAX(mp.timestamp)) + 1 AS expected_candles,
            DATEDIFF(HOUR, MIN(mp.timestamp), MAX(mp.timestamp)) + 1 - COUNT(*) AS missing_candles,
            CAST(COUNT(*) * 100.0 / NULLIF(DATEDIFF(HOUR, MIN(mp.timestamp), MAX(mp.timestamp)) + 1, 0) AS DECIMAL(5,2)) AS coverage_percent
        FROM crypto.market_prices AS mp
        INNER JOIN crypto.trading_pairs AS tp
            ON tp.id = mp.trading_pair_id
        GROUP BY tp.symbol
    )
    SELECT
        currency_pair,
        actual_candles,
        expected_candles,
        missing_candles,
        coverage_percent,
        CASE
            WHEN coverage_percent < 90 THEN 'HIGH PRIORITY - Full re-ingestion recommended'
            WHEN coverage_percent < 95 THEN 'MEDIUM PRIORITY - Gap filling recommended'
            WHEN coverage_percent < 99 THEN 'LOW PRIORITY - Minor gaps'
            ELSE 'GOOD - No action needed'
        END AS recommendation
    FROM coverage
    WHERE coverage_percent < 99
    ORDER BY coverage_percent ASC;
    
    IF @@ROWCOUNT = 0
    BEGIN
        PRINT 'All currency pairs have >= 99% coverage - No re-ingestion needed!';
    END;
END
ELSE
BEGIN
    PRINT 'ERROR: Required tables not found';
END;

PRINT '';
PRINT '============================================================';
PRINT 'Market Prices Validation Complete';
PRINT '============================================================';

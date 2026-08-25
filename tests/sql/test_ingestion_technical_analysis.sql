/*
Technical Analysis Ingestion Validation - Simplified

Purpose:
- Quick count of analysis records by currency pair
- Identify missing analysis records (compared to market_prices)
- Simple summary for re-calculation decisions

This script is read-only and intended for Azure SQL / SQL Server.
*/

SET NOCOUNT ON;

PRINT '============================================================';
PRINT 'Technical Analysis Ingestion Summary';
PRINT '============================================================';
PRINT '';

-- ============================================================
-- 1. Overall Summary
-- ============================================================
PRINT '1) Overall Summary';

IF OBJECT_ID('crypto.technical_analysis', 'U') IS NOT NULL
BEGIN
    SELECT
        COUNT(*) AS total_analysis_records,
        COUNT(DISTINCT trading_pair_id) AS distinct_pairs,
        MIN(timestamp) AS first_analysis_utc,
        MAX(timestamp) AS latest_analysis_utc,
        DATEDIFF(DAY, MIN(timestamp), MAX(timestamp)) AS days_span,
        COUNT(DISTINCT calculation_version) AS versions,
        COUNT(CASE WHEN ema_200 IS NOT NULL THEN 1 END) AS records_with_ema,
        COUNT(CASE WHEN rsi_14 IS NOT NULL THEN 1 END) AS records_with_rsi,
        COUNT(CASE WHEN macd IS NOT NULL THEN 1 END) AS records_with_macd
    FROM crypto.technical_analysis;
END
ELSE
BEGIN
    PRINT 'ERROR: crypto.technical_analysis table not found';
END;

PRINT '';
PRINT '============================================================';

-- ============================================================
-- 2. Analysis Coverage by Currency Pair
-- ============================================================
PRINT '2) Analysis Coverage by Currency Pair';

IF OBJECT_ID('crypto.market_prices', 'U') IS NOT NULL
   AND OBJECT_ID('crypto.technical_analysis', 'U') IS NOT NULL
   AND OBJECT_ID('crypto.trading_pairs', 'U') IS NOT NULL
BEGIN
    WITH warmup_threshold AS (
        -- After 200 hours (EMA 200 requirement)
        SELECT
            tp.id AS trading_pair_id,
            tp.symbol,
            MIN(mp.timestamp) AS first_candle,
            DATEADD(HOUR, 200, MIN(mp.timestamp)) AS warmup_complete
        FROM crypto.market_prices AS mp
        INNER JOIN crypto.trading_pairs AS tp
            ON tp.id = mp.trading_pair_id
        GROUP BY tp.id, tp.symbol
    )
    SELECT
        tp.symbol AS currency_pair,
        COUNT(mp.id) AS market_prices_after_warmup,
        COUNT(ta.id) AS analysis_records,
        COUNT(mp.id) - COUNT(ta.id) AS missing_analysis,
        CAST(CASE
            WHEN COUNT(mp.id) = 0 THEN 0
            ELSE COUNT(ta.id) * 100.0 / COUNT(mp.id)
        END AS DECIMAL(5,2)) AS coverage_percent,
        w.warmup_complete,
        MAX(ta.timestamp) AS latest_analysis,
        DATEDIFF(HOUR, MAX(ta.timestamp), SYSUTCDATETIME()) AS hours_since_latest
    FROM crypto.trading_pairs AS tp
    INNER JOIN warmup_threshold AS w
        ON w.trading_pair_id = tp.id
    LEFT JOIN crypto.market_prices AS mp
        ON mp.trading_pair_id = tp.id
        AND mp.timestamp >= w.warmup_complete
    LEFT JOIN crypto.technical_analysis AS ta
        ON ta.market_price_id = mp.id
    GROUP BY tp.symbol, w.warmup_complete
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
PRINT '3) Analysis Gap Summary by Currency Pair';

IF OBJECT_ID('crypto.technical_analysis', 'U') IS NOT NULL
   AND OBJECT_ID('crypto.trading_pairs', 'U') IS NOT NULL
BEGIN
    WITH ordered_analysis AS (
        SELECT
            ta.trading_pair_id,
            tp.symbol,
            ta.timestamp,
            LEAD(ta.timestamp) OVER (
                PARTITION BY ta.trading_pair_id
                ORDER BY ta.timestamp
            ) AS next_timestamp
        FROM crypto.technical_analysis AS ta
        INNER JOIN crypto.trading_pairs AS tp
            ON tp.id = ta.trading_pair_id
    ),
    gaps AS (
        SELECT
            symbol,
            DATEDIFF(HOUR, timestamp, next_timestamp) AS hours_gap
        FROM ordered_analysis
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
        PRINT 'No gaps detected - all hourly analysis present!';
    END;
END
ELSE
BEGIN
    PRINT 'ERROR: Required tables not found';
END;

PRINT '';
PRINT '============================================================';

-- ============================================================
-- 4. Re-Calculation Recommendations
-- ============================================================
PRINT '4) Re-Calculation Recommendations';

IF OBJECT_ID('crypto.market_prices', 'U') IS NOT NULL
   AND OBJECT_ID('crypto.technical_analysis', 'U') IS NOT NULL
   AND OBJECT_ID('crypto.trading_pairs', 'U') IS NOT NULL
BEGIN
    WITH warmup_threshold AS (
        SELECT
            tp.id AS trading_pair_id,
            tp.symbol,
            DATEADD(HOUR, 200, MIN(mp.timestamp)) AS warmup_complete
        FROM crypto.market_prices AS mp
        INNER JOIN crypto.trading_pairs AS tp
            ON tp.id = mp.trading_pair_id
        GROUP BY tp.id, tp.symbol
    ),
    coverage AS (
        SELECT
            tp.symbol AS currency_pair,
            COUNT(mp.id) AS market_prices_after_warmup,
            COUNT(ta.id) AS analysis_records,
            COUNT(mp.id) - COUNT(ta.id) AS missing_analysis,
            CAST(CASE
                WHEN COUNT(mp.id) = 0 THEN 0
                ELSE COUNT(ta.id) * 100.0 / COUNT(mp.id)
            END AS DECIMAL(5,2)) AS coverage_percent
        FROM crypto.trading_pairs AS tp
        INNER JOIN warmup_threshold AS w
            ON w.trading_pair_id = tp.id
        LEFT JOIN crypto.market_prices AS mp
            ON mp.trading_pair_id = tp.id
            AND mp.timestamp >= w.warmup_complete
        LEFT JOIN crypto.technical_analysis AS ta
            ON ta.market_price_id = mp.id
        GROUP BY tp.symbol
    )
    SELECT
        currency_pair,
        market_prices_after_warmup,
        analysis_records,
        missing_analysis,
        coverage_percent,
        CASE
            WHEN coverage_percent < 50 THEN 'HIGH PRIORITY - Full calculation recommended'
            WHEN coverage_percent < 90 THEN 'MEDIUM PRIORITY - Incremental calculation recommended'
            WHEN coverage_percent < 98 THEN 'LOW PRIORITY - Gap filling recommended'
            ELSE 'GOOD - No action needed'
        END AS recommendation,
        'python scripts/calculate_technical_analysis.py --mode ' + 
            CASE WHEN coverage_percent < 90 THEN 'historical' ELSE 'incremental' END + 
            ' --pair ' + currency_pair AS suggested_command
    FROM coverage
    WHERE coverage_percent < 98
    ORDER BY coverage_percent ASC;
    
    IF @@ROWCOUNT = 0
    BEGIN
        PRINT 'All currency pairs have >= 98% analysis coverage - No re-calculation needed!';
    END;
END
ELSE
BEGIN
    PRINT 'ERROR: Required tables not found';
END;

PRINT '';
PRINT '============================================================';
PRINT 'Technical Analysis Validation Complete';
PRINT '============================================================';

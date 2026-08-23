/*
CryptoQuant ingestion summary checks

Purpose:
- Verify the core ingestion tables exist.
- Summarize row counts and latest loaded market data.
- Check tracked pairs against trading_pairs.
- Highlight duplicate, invalid, or missing daily OHLCV data.

This script is read-only and is intended for Azure SQL / SQL Server.
*/

SET NOCOUNT ON;

DECLARE @ExpectedGranularity VARCHAR(20) = 'daily';
DECLARE @MaxGapDays INT = CASE WHEN @ExpectedGranularity = 'daily' THEN 1 ELSE 1 END;

PRINT '============================================================';
PRINT 'CryptoQuant Ingestion Summary';
PRINT '============================================================';

SELECT
    DB_NAME() AS database_name,
    SUSER_SNAME() AS login_name,
    SYSUTCDATETIME() AS checked_at_utc;

PRINT '1) Required table presence';

SELECT
    v.schema_name,
    v.table_name,
    CASE
        WHEN t.object_id IS NULL THEN 'MISSING'
        ELSE 'OK'
    END AS status
FROM (
    VALUES
        ('crypto', 'assets'),
        ('crypto', 'trading_pairs'),
        ('crypto', 'tracked_pairs'),
        ('crypto', 'market_prices')
) AS v(schema_name, table_name)
LEFT JOIN sys.schemas AS s
    ON s.name = v.schema_name
LEFT JOIN sys.tables AS t
    ON t.schema_id = s.schema_id
   AND t.name = v.table_name
ORDER BY v.schema_name, v.table_name;

PRINT '2) Alembic migration version';

IF OBJECT_ID('dbo.alembic_version', 'U') IS NOT NULL
BEGIN
    SELECT version_num FROM dbo.alembic_version;
END
ELSE
BEGIN
    SELECT 'dbo.alembic_version table not found' AS warning;
END;

PRINT '3) Core table row counts';

SELECT
    v.schema_name + '.' + v.table_name AS table_name,
    CASE
        WHEN t.object_id IS NULL THEN NULL
        ELSE SUM(p.rows)
    END AS estimated_row_count,
    CASE
        WHEN t.object_id IS NULL THEN 'MISSING'
        ELSE 'OK'
    END AS status
FROM (
    VALUES
        ('crypto', 'assets'),
        ('crypto', 'trading_pairs'),
        ('crypto', 'tracked_pairs'),
        ('crypto', 'market_prices')
) AS v(schema_name, table_name)
LEFT JOIN sys.schemas AS s
    ON s.name = v.schema_name
LEFT JOIN sys.tables AS t
    ON t.schema_id = s.schema_id
   AND t.name = v.table_name
LEFT JOIN sys.partitions AS p
    ON p.object_id = t.object_id
   AND p.index_id IN (0, 1)
GROUP BY
    v.schema_name,
    v.table_name,
    t.object_id
ORDER BY table_name;

PRINT '4) Active tracked pairs and whether they exist in trading_pairs';

IF OBJECT_ID('crypto.tracked_pairs', 'U') IS NOT NULL
   AND OBJECT_ID('crypto.trading_pairs', 'U') IS NOT NULL
BEGIN
    SELECT
        tr.product_id,
        tr.symbol AS tracked_symbol,
        tr.is_tracking_active,
        tp.id AS trading_pair_id,
        tp.symbol AS trading_pair_symbol,
        tp.status,
        tp.trading_disabled,
        tp.active,
        CASE
            WHEN tp.id IS NULL THEN 'MISSING_FROM_TRADING_PAIRS'
            WHEN tp.active = 0 OR tp.trading_disabled = 1 THEN 'NOT_ACTIVE_OR_DISABLED'
            ELSE 'OK'
        END AS readiness_status
    FROM crypto.tracked_pairs AS tr
    LEFT JOIN crypto.trading_pairs AS tp
        ON tp.symbol = tr.product_id
    ORDER BY tr.is_tracking_active DESC, tr.product_id;
END
ELSE
BEGIN
    SELECT 'tracked_pairs or trading_pairs table missing' AS warning;
END;

PRINT '5) Market data coverage by tracked pair';

IF OBJECT_ID('crypto.tracked_pairs', 'U') IS NOT NULL
   AND OBJECT_ID('crypto.trading_pairs', 'U') IS NOT NULL
   AND OBJECT_ID('crypto.market_prices', 'U') IS NOT NULL
BEGIN
    SELECT
        tr.product_id,
        tr.is_tracking_active,
        tp.id AS trading_pair_id,
        COUNT(mp.id) AS candle_count,
        MIN(mp.timestamp) AS first_candle_utc,
        MAX(mp.timestamp) AS latest_candle_utc,
        DATEDIFF(DAY, MAX(mp.timestamp), SYSUTCDATETIME()) AS days_since_latest_candle,
        MIN(mp.[close]) AS min_close,
        MAX(mp.[close]) AS max_close,
        SUM(CAST(mp.volume AS DECIMAL(38, 8))) AS total_volume
    FROM crypto.tracked_pairs AS tr
    LEFT JOIN crypto.trading_pairs AS tp
        ON tp.symbol = tr.product_id
    LEFT JOIN crypto.market_prices AS mp
        ON mp.trading_pair_id = tp.id
    GROUP BY
        tr.product_id,
        tr.is_tracking_active,
        tp.id
    ORDER BY tr.product_id;
END
ELSE
BEGIN
    SELECT 'tracked_pairs, trading_pairs, or market_prices table missing' AS warning;
END;

PRINT '6) Market data coverage by all loaded trading pairs';

IF OBJECT_ID('crypto.trading_pairs', 'U') IS NOT NULL
   AND OBJECT_ID('crypto.market_prices', 'U') IS NOT NULL
BEGIN
    SELECT TOP (50)
        tp.symbol,
        COUNT(mp.id) AS candle_count,
        MIN(mp.timestamp) AS first_candle_utc,
        MAX(mp.timestamp) AS latest_candle_utc,
        DATEDIFF(DAY, MAX(mp.timestamp), SYSUTCDATETIME()) AS days_since_latest_candle
    FROM crypto.trading_pairs AS tp
    INNER JOIN crypto.market_prices AS mp
        ON mp.trading_pair_id = tp.id
    GROUP BY tp.symbol
    ORDER BY candle_count DESC, tp.symbol;
END
ELSE
BEGIN
    SELECT 'trading_pairs or market_prices table missing' AS warning;
END;

PRINT '7) Duplicate candle check';

IF OBJECT_ID('crypto.market_prices', 'U') IS NOT NULL
BEGIN
    SELECT TOP (100)
        trading_pair_id,
        timestamp,
        COUNT(*) AS duplicate_count
    FROM crypto.market_prices
    GROUP BY trading_pair_id, timestamp
    HAVING COUNT(*) > 1
    ORDER BY duplicate_count DESC, trading_pair_id, timestamp;
END
ELSE
BEGIN
    SELECT 'market_prices table missing' AS warning;
END;

PRINT '8) Invalid OHLCV check';

IF OBJECT_ID('crypto.trading_pairs', 'U') IS NOT NULL
   AND OBJECT_ID('crypto.market_prices', 'U') IS NOT NULL
BEGIN
    SELECT TOP (100)
        tp.symbol,
        mp.timestamp,
        mp.[open],
        mp.high,
        mp.low,
        mp.[close],
        mp.volume,
        CASE
            WHEN mp.low > mp.high THEN 'LOW_GT_HIGH'
            WHEN mp.[open] < mp.low OR mp.[open] > mp.high THEN 'OPEN_OUTSIDE_RANGE'
            WHEN mp.[close] < mp.low OR mp.[close] > mp.high THEN 'CLOSE_OUTSIDE_RANGE'
            WHEN mp.volume < 0 THEN 'NEGATIVE_VOLUME'
            ELSE 'OK'
        END AS issue
    FROM crypto.market_prices AS mp
    INNER JOIN crypto.trading_pairs AS tp
        ON tp.id = mp.trading_pair_id
    WHERE mp.low > mp.high
       OR mp.[open] < mp.low
       OR mp.[open] > mp.high
       OR mp.[close] < mp.low
       OR mp.[close] > mp.high
       OR mp.volume < 0
    ORDER BY mp.timestamp DESC, tp.symbol;
END
ELSE
BEGIN
    SELECT 'trading_pairs or market_prices table missing' AS warning;
END;

PRINT '9) Daily gap check for active tracked pairs';

IF OBJECT_ID('crypto.tracked_pairs', 'U') IS NOT NULL
   AND OBJECT_ID('crypto.trading_pairs', 'U') IS NOT NULL
   AND OBJECT_ID('crypto.market_prices', 'U') IS NOT NULL
BEGIN
    WITH ordered_candles AS (
        SELECT
            tp.symbol,
            mp.timestamp,
            LEAD(mp.timestamp) OVER (
                PARTITION BY tp.symbol
                ORDER BY mp.timestamp
            ) AS next_timestamp
        FROM crypto.tracked_pairs AS tr
        INNER JOIN crypto.trading_pairs AS tp
            ON tp.symbol = tr.product_id
        INNER JOIN crypto.market_prices AS mp
            ON mp.trading_pair_id = tp.id
        WHERE tr.is_tracking_active = 1
    )
    SELECT TOP (100)
        symbol,
        timestamp AS gap_start_utc,
        next_timestamp AS gap_end_utc,
        DATEDIFF(DAY, timestamp, next_timestamp) AS gap_days
    FROM ordered_candles
    WHERE next_timestamp IS NOT NULL
      AND DATEDIFF(DAY, timestamp, next_timestamp) > @MaxGapDays
    ORDER BY symbol, timestamp;
END
ELSE
BEGIN
    SELECT 'tracked_pairs, trading_pairs, or market_prices table missing' AS warning;
END;

PRINT '10) Latest candles for active tracked pairs';

IF OBJECT_ID('crypto.tracked_pairs', 'U') IS NOT NULL
   AND OBJECT_ID('crypto.trading_pairs', 'U') IS NOT NULL
   AND OBJECT_ID('crypto.market_prices', 'U') IS NOT NULL
BEGIN
    WITH ranked AS (
        SELECT
            tp.symbol,
            mp.timestamp,
            mp.[open],
            mp.high,
            mp.low,
            mp.[close],
            mp.volume,
            mp.data_source,
            ROW_NUMBER() OVER (
                PARTITION BY tp.symbol
                ORDER BY mp.timestamp DESC
            ) AS row_number
        FROM crypto.tracked_pairs AS tr
        INNER JOIN crypto.trading_pairs AS tp
            ON tp.symbol = tr.product_id
        INNER JOIN crypto.market_prices AS mp
            ON mp.trading_pair_id = tp.id
        WHERE tr.is_tracking_active = 1
    )
    SELECT
        symbol,
        timestamp,
        [open],
        high,
        low,
        [close],
        volume,
        data_source
    FROM ranked
    WHERE row_number <= 5
    ORDER BY symbol, timestamp DESC;
END
ELSE
BEGIN
    SELECT 'tracked_pairs, trading_pairs, or market_prices table missing' AS warning;
END;

PRINT '============================================================';
PRINT 'Ingestion summary complete';
PRINT '============================================================';



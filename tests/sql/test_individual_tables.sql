/*
CryptoQuant individual table checks

Purpose:
- Inspect each core table independently.
- Show schema, row counts, sample records, and common integrity checks.

This script is read-only and is intended for Azure SQL / SQL Server.
*/

SET NOCOUNT ON;

DECLARE @SampleRows INT = 25;

PRINT '============================================================';
PRINT 'CryptoQuant Individual Table Checks';
PRINT '============================================================';

SELECT
    DB_NAME() AS database_name,
    SYSUTCDATETIME() AS checked_at_utc;

PRINT '0) Available crypto schema tables';

SELECT
    s.name AS schema_name,
    t.name AS table_name,
    SUM(p.rows) AS estimated_rows
FROM sys.tables AS t
INNER JOIN sys.schemas AS s
    ON s.schema_id = t.schema_id
LEFT JOIN sys.partitions AS p
    ON p.object_id = t.object_id
   AND p.index_id IN (0, 1)
WHERE s.name = 'crypto'
GROUP BY s.name, t.name
ORDER BY s.name, t.name;

PRINT '1) Column definitions for core tables';

SELECT
    c.TABLE_SCHEMA,
    c.TABLE_NAME,
    c.ORDINAL_POSITION,
    c.COLUMN_NAME,
    c.DATA_TYPE,
    c.CHARACTER_MAXIMUM_LENGTH,
    c.NUMERIC_PRECISION,
    c.NUMERIC_SCALE,
    c.IS_NULLABLE,
    c.COLUMN_DEFAULT
FROM INFORMATION_SCHEMA.COLUMNS AS c
WHERE c.TABLE_SCHEMA = 'crypto'
  AND c.TABLE_NAME IN ('assets', 'trading_pairs', 'tracked_pairs', 'market_prices')
ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION;

PRINT '2) crypto.assets';

IF OBJECT_ID('crypto.assets', 'U') IS NOT NULL
BEGIN
    SELECT COUNT_BIG(*) AS total_assets FROM crypto.assets;

    SELECT
        active,
        asset_type,
        COUNT(*) AS asset_count
    FROM crypto.assets
    GROUP BY active, asset_type
    ORDER BY active DESC, asset_type;

    SELECT TOP (@SampleRows)
        id,
        product_id,
        symbol,
        name,
        display_symbol,
        asset_type,
        decimals,
        active,
        created_at,
        updated_at
    FROM crypto.assets
    ORDER BY symbol;

    SELECT
        symbol,
        COUNT(*) AS duplicate_count
    FROM crypto.assets
    GROUP BY symbol
    HAVING COUNT(*) > 1
    ORDER BY duplicate_count DESC, symbol;
END
ELSE
BEGIN
    SELECT 'crypto.assets table missing' AS warning;
END;

PRINT '3) crypto.trading_pairs';

IF OBJECT_ID('crypto.trading_pairs', 'U') IS NOT NULL
BEGIN
    SELECT COUNT_BIG(*) AS total_trading_pairs FROM crypto.trading_pairs;

    SELECT
        status,
        active,
        trading_disabled,
        COUNT(*) AS pair_count
    FROM crypto.trading_pairs
    GROUP BY status, active, trading_disabled
    ORDER BY pair_count DESC;

    SELECT TOP (@SampleRows)
        tp.id,
        tp.symbol,
        base.symbol AS base_asset,
        quote.symbol AS quote_asset,
        tp.status,
        tp.trading_disabled,
        tp.active,
        tp.base_min_size,
        tp.base_max_size,
        tp.quote_increment,
        tp.created_at,
        tp.updated_at
    FROM crypto.trading_pairs AS tp
    LEFT JOIN crypto.assets AS base
        ON base.id = tp.base_asset_id
    LEFT JOIN crypto.assets AS quote
        ON quote.id = tp.quote_asset_id
    ORDER BY tp.symbol;

    SELECT
        tp.id,
        tp.symbol,
        tp.base_asset_id,
        tp.quote_asset_id,
        CASE
            WHEN base.id IS NULL THEN 'MISSING_BASE_ASSET'
            WHEN quote.id IS NULL THEN 'MISSING_QUOTE_ASSET'
            ELSE 'OK'
        END AS issue
    FROM crypto.trading_pairs AS tp
    LEFT JOIN crypto.assets AS base
        ON base.id = tp.base_asset_id
    LEFT JOIN crypto.assets AS quote
        ON quote.id = tp.quote_asset_id
    WHERE base.id IS NULL
       OR quote.id IS NULL
    ORDER BY tp.symbol;

    SELECT
        symbol,
        COUNT(*) AS duplicate_count
    FROM crypto.trading_pairs
    GROUP BY symbol
    HAVING COUNT(*) > 1
    ORDER BY duplicate_count DESC, symbol;
END
ELSE
BEGIN
    SELECT 'crypto.trading_pairs table missing' AS warning;
END;

PRINT '4) crypto.tracked_pairs';

IF OBJECT_ID('crypto.tracked_pairs', 'U') IS NOT NULL
BEGIN
    SELECT COUNT_BIG(*) AS total_tracked_pairs FROM crypto.tracked_pairs;

    SELECT
        is_tracking_active,
        COUNT(*) AS tracked_pair_count
    FROM crypto.tracked_pairs
    GROUP BY is_tracking_active
    ORDER BY is_tracking_active DESC;

    SELECT TOP (@SampleRows)
        tr.id,
        tr.product_id,
        tr.symbol,
        tr.is_tracking_active,
        tp.id AS trading_pair_id,
        tp.active AS trading_pair_active,
        tp.trading_disabled,
        tr.created_at,
        tr.modified_at,
        CASE
            WHEN tp.id IS NULL THEN 'MISSING_FROM_TRADING_PAIRS'
            WHEN tp.active = 0 OR tp.trading_disabled = 1 THEN 'NOT_ACTIVE_OR_DISABLED'
            ELSE 'OK'
        END AS readiness_status
    FROM crypto.tracked_pairs AS tr
    LEFT JOIN crypto.trading_pairs AS tp
        ON tp.symbol = tr.product_id
    ORDER BY tr.product_id;

    SELECT
        product_id,
        COUNT(*) AS duplicate_count
    FROM crypto.tracked_pairs
    GROUP BY product_id
    HAVING COUNT(*) > 1
    ORDER BY duplicate_count DESC, product_id;
END
ELSE
BEGIN
    SELECT 'crypto.tracked_pairs table missing' AS warning;
END;

PRINT '5) crypto.market_prices';

IF OBJECT_ID('crypto.market_prices', 'U') IS NOT NULL
BEGIN
    SELECT
        COUNT_BIG(*) AS total_market_prices,
        MIN(timestamp) AS first_candle_utc,
        MAX(timestamp) AS latest_candle_utc,
        MIN(created_at) AS first_inserted_at_utc,
        MAX(created_at) AS latest_inserted_at_utc
    FROM crypto.market_prices;

    SELECT
        data_source,
        COUNT(*) AS candle_count,
        MIN(timestamp) AS first_candle_utc,
        MAX(timestamp) AS latest_candle_utc
    FROM crypto.market_prices
    GROUP BY data_source
    ORDER BY candle_count DESC;

    SELECT TOP (@SampleRows)
        mp.id,
        tp.symbol,
        mp.trading_pair_id,
        mp.timestamp,
        mp.[open],
        mp.high,
        mp.low,
        mp.[close],
        mp.volume,
        mp.data_source,
        mp.created_at
    FROM crypto.market_prices AS mp
    LEFT JOIN crypto.trading_pairs AS tp
        ON tp.id = mp.trading_pair_id
    ORDER BY mp.timestamp DESC, tp.symbol;

    SELECT TOP (100)
        tp.symbol,
        mp.trading_pair_id,
        COUNT(*) AS candle_count,
        MIN(mp.timestamp) AS first_candle_utc,
        MAX(mp.timestamp) AS latest_candle_utc
    FROM crypto.market_prices AS mp
    LEFT JOIN crypto.trading_pairs AS tp
        ON tp.id = mp.trading_pair_id
    GROUP BY tp.symbol, mp.trading_pair_id
    ORDER BY candle_count DESC, tp.symbol;

    SELECT
        mp.trading_pair_id,
        mp.timestamp,
        COUNT(*) AS duplicate_count
    FROM crypto.market_prices AS mp
    GROUP BY mp.trading_pair_id, mp.timestamp
    HAVING COUNT(*) > 1
    ORDER BY duplicate_count DESC, mp.trading_pair_id, mp.timestamp;

    SELECT TOP (100)
        mp.id,
        mp.trading_pair_id,
        mp.timestamp,
        CASE
            WHEN tp.id IS NULL THEN 'MISSING_TRADING_PAIR'
            WHEN mp.low > mp.high THEN 'LOW_GT_HIGH'
            WHEN mp.[open] < mp.low OR mp.[open] > mp.high THEN 'OPEN_OUTSIDE_RANGE'
            WHEN mp.[close] < mp.low OR mp.[close] > mp.high THEN 'CLOSE_OUTSIDE_RANGE'
            WHEN mp.volume < 0 THEN 'NEGATIVE_VOLUME'
            ELSE 'OK'
        END AS issue,
        mp.[open],
        mp.high,
        mp.low,
        mp.[close],
        mp.volume
    FROM crypto.market_prices AS mp
    LEFT JOIN crypto.trading_pairs AS tp
        ON tp.id = mp.trading_pair_id
    WHERE tp.id IS NULL
       OR mp.low > mp.high
       OR mp.[open] < mp.low
       OR mp.[open] > mp.high
       OR mp.[close] < mp.low
       OR mp.[close] > mp.high
       OR mp.volume < 0
    ORDER BY mp.timestamp DESC;
END
ELSE
BEGIN
    SELECT 'crypto.market_prices table missing' AS warning;
END;

PRINT '6) Indexes and constraints for core tables';

SELECT
    s.name AS schema_name,
    t.name AS table_name,
    i.name AS index_name,
    i.type_desc,
    i.is_unique,
    i.is_primary_key,
    i.is_unique_constraint
FROM sys.indexes AS i
INNER JOIN sys.tables AS t
    ON t.object_id = i.object_id
INNER JOIN sys.schemas AS s
    ON s.schema_id = t.schema_id
WHERE s.name = 'crypto'
  AND t.name IN ('assets', 'trading_pairs', 'tracked_pairs', 'market_prices')
  AND i.name IS NOT NULL
ORDER BY t.name, i.name;

PRINT '============================================================';
PRINT 'Individual table checks complete';
PRINT '============================================================';

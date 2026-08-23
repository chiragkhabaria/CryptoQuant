-- =====================================================================
-- CryptoQuant Candle Data Cleanup Script
-- =====================================================================
-- WARNING: This deletes ALL candle data from market_prices table.
-- Backup your data before running!
-- =====================================================================

USE [fin-market-db];
GO

-- Show current state
PRINT 'Candles before cleanup:';
SELECT COUNT(*) AS total_candles FROM crypto.market_prices;
PRINT '';

-- Delete all candle data
BEGIN TRANSACTION;

DELETE FROM crypto.market_prices;

PRINT 'Candles deleted. Verifying...';
SELECT COUNT(*) AS remaining_candles FROM crypto.market_prices;
PRINT '';

-- Uncomment one of the following:
-- COMMIT;      -- To save the deletion
ROLLBACK;    -- To undo the deletion (default for safety)

PRINT 'Cleanup complete.';
-- PRINT '';
-- PRINT 'Deleting all records from crypto.market_prices...';
-- PRINT '';
--
-- -- Delete all candle data
-- DELETE FROM crypto.market_prices;
--
-- DECLARE @deleted_count INT = @@ROWCOUNT;
-- PRINT 'Deleted ' + CAST(@deleted_count AS VARCHAR(20)) + ' records.';
-- PRINT '';
--
-- -- Verify deletion
-- PRINT '---------------------------------------------------------------------';
-- PRINT 'VERIFICATION (After Delete):';
-- PRINT '---------------------------------------------------------------------';
--
-- SELECT 
--     COUNT(*) AS remaining_candles,
--     CASE 
--         WHEN COUNT(*) = 0 THEN 'SUCCESS: All candles deleted'
--         ELSE 'WARNING: ' + CAST(COUNT(*) AS VARCHAR(20)) + ' candles remain'
--     END AS status
-- FROM crypto.market_prices;
--
-- PRINT '';
-- PRINT '=====================================================================';
-- PRINT 'TRANSACTION DECISION';
-- PRINT '=====================================================================';
-- PRINT '';
-- PRINT 'Review the verification results above.';
-- PRINT '';
-- PRINT 'To COMMIT (make deletion permanent):';
-- PRINT '  1. Uncomment the COMMIT line below';
-- PRINT '  2. Comment out the ROLLBACK line';
-- PRINT '  3. Execute';
-- PRINT '';
-- PRINT 'To ROLLBACK (undo deletion):';
-- PRINT '  1. Keep ROLLBACK uncommented (default)';
-- PRINT '  2. Execute';
-- PRINT '';
-- PRINT '---------------------------------------------------------------------';
--
-- -- Default action: ROLLBACK (safe)
-- -- To commit, comment out ROLLBACK and uncomment COMMIT
-- ROLLBACK TRANSACTION CleanupTransaction;
-- -- COMMIT TRANSACTION CleanupTransaction;
--
-- PRINT '';
-- PRINT '=====================================================================';

-- =====================================================================
-- Step 3: Post-Cleanup Verification (Only runs if committed)
-- =====================================================================

PRINT '';
PRINT '=====================================================================';
PRINT 'POST-CLEANUP STATE';
PRINT '=====================================================================';
PRINT '';

SELECT 
    COUNT(*) AS total_candles,
    CASE 
        WHEN COUNT(*) = 0 THEN 'SUCCESS: Database is clean, ready for historical ingestion'
        ELSE 'INFO: ' + CAST(COUNT(*) AS VARCHAR(20)) + ' candles present'
    END AS status
FROM crypto.market_prices;

PRINT '';
PRINT '=====================================================================';
PRINT 'CLEANUP SCRIPT EXECUTION COMPLETE';
PRINT '=====================================================================';
PRINT '';
PRINT 'Instructions for Next Steps:';
PRINT '';
PRINT '1. If cleanup was successful (0 records), proceed with historical ingestion:';
PRINT '   cd D:\crypto';
PRINT '   .\.venv\Scripts\Activate.ps1';
PRINT '   python -c "from cryptoquant.ingestion.historic import run_ingestion; run_ingestion(days=1095)"';
PRINT '';
PRINT '2. Monitor progress in logs:';
PRINT '   Get-Content logs\*.log -Tail 100 -Wait';
PRINT '';
PRINT '3. Expected duration: 2-6 hours for 3 years of data';
PRINT '';
PRINT '=====================================================================';

GO

-- =====================================================================
-- Alternative: Quick Cleanup (No Transaction, No Safety Checks)
-- =====================================================================
-- WARNING: USE ONLY IF YOU ARE ABSOLUTELY CERTAIN
-- This version has no rollback capability
-- =====================================================================
--
-- -- Uncomment to execute immediate cleanup
-- -- TRUNCATE TABLE crypto.market_prices;
-- -- PRINT 'Table truncated successfully.';
--
-- =====================================================================

-- =====================================================================
-- Utility: Check Table Size
-- =====================================================================

PRINT '';
PRINT 'Table Size Information:';
PRINT '---------------------------------------------------------------------';

SELECT 
    t.NAME AS table_name,
    s.Name AS schema_name,
    p.rows AS row_count,
    CAST(ROUND(((SUM(a.total_pages) * 8) / 1024.00), 2) AS NUMERIC(36, 2)) AS total_space_mb,
    CAST(ROUND(((SUM(a.used_pages) * 8) / 1024.00), 2) AS NUMERIC(36, 2)) AS used_space_mb,
    CAST(ROUND(((SUM(a.total_pages) - SUM(a.used_pages)) * 8) / 1024.00, 2) AS NUMERIC(36, 2)) AS unused_space_mb
FROM 
    sys.tables t
INNER JOIN 
    sys.indexes i ON t.OBJECT_ID = i.object_id
INNER JOIN 
    sys.partitions p ON i.object_id = p.OBJECT_ID AND i.index_id = p.index_id
INNER JOIN 
    sys.allocation_units a ON p.partition_id = a.container_id
INNER JOIN 
    sys.schemas s ON t.schema_id = s.schema_id
WHERE 
    t.NAME = 'market_prices'
    AND s.Name = 'crypto'
    AND t.is_ms_shipped = 0
    AND i.OBJECT_ID > 255 
GROUP BY 
    t.Name, s.Name, p.Rows
ORDER BY 
    total_space_mb DESC;

GO

-- =====================================================================
-- End of Script
-- =====================================================================

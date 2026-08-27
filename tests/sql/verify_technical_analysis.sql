-- Verify technical_analysis table structure
-- Run this to confirm Phase 2 database setup is complete

USE [fin-market-db];
GO

-- 1. Check if table exists
IF OBJECT_ID('crypto.technical_analysis', 'U') IS NOT NULL
BEGIN
    PRINT '✓ crypto.technical_analysis table exists'
END
ELSE
BEGIN
    PRINT '✗ crypto.technical_analysis table NOT FOUND'
END
GO

-- 2. Show table structure
SELECT 
    c.name AS column_name,
    t.name AS data_type,
    c.max_length,
    c.precision,
    c.scale,
    c.is_nullable,
    c.is_identity
FROM sys.columns c
INNER JOIN sys.types t ON c.user_type_id = t.user_type_id
INNER JOIN sys.tables tbl ON c.object_id = tbl.object_id
INNER JOIN sys.schemas s ON tbl.schema_id = s.schema_id
WHERE s.name = 'crypto' 
  AND tbl.name = 'technical_analysis'
ORDER BY c.column_id;
GO

-- 3. Show indexes
SELECT 
    i.name AS index_name,
    i.type_desc,
    i.is_unique,
    i.is_primary_key,
    COL_NAME(ic.object_id, ic.column_id) AS column_name
FROM sys.indexes i
INNER JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
INNER JOIN sys.tables t ON i.object_id = t.object_id
INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
WHERE s.name = 'crypto' 
  AND t.name = 'technical_analysis'
  AND i.name IS NOT NULL
ORDER BY i.name, ic.key_ordinal;
GO

-- 4. Show foreign keys
SELECT 
    fk.name AS foreign_key_name,
    OBJECT_NAME(fk.parent_object_id) AS table_name,
    COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS column_name,
    OBJECT_NAME(fk.referenced_object_id) AS referenced_table,
    COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS referenced_column
FROM sys.foreign_keys fk
INNER JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
INNER JOIN sys.tables t ON fk.parent_object_id = t.object_id
INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
WHERE s.name = 'crypto' 
  AND t.name = 'technical_analysis';
GO

-- 5. Show constraints
SELECT 
    kc.name AS constraint_name,
    kc.type_desc,
    COL_NAME(ic.object_id, ic.column_id) AS column_name
FROM sys.key_constraints kc
INNER JOIN sys.index_columns ic ON kc.parent_object_id = ic.object_id AND kc.unique_index_id = ic.index_id
INNER JOIN sys.tables t ON kc.parent_object_id = t.object_id
INNER JOIN sys.schemas s ON t.schema_id = s.schema_id
WHERE s.name = 'crypto' 
  AND t.name = 'technical_analysis'
ORDER BY kc.name, ic.key_ordinal;
GO

PRINT 'Phase 2 database verification complete';

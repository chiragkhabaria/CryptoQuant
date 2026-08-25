# Alembic Database Migration Guide

## Overview

This guide explains how to manage database schema changes using Alembic migrations.

## Current Database Structure

### Market Prices Table

The `crypto.market_prices` table uses an optimal design for time-series data:

```sql
CREATE TABLE crypto.market_prices (
    id INT IDENTITY(1,1) PRIMARY KEY,           -- Auto-increment surrogate key
    trading_pair_id INT NOT NULL,               -- Foreign key to trading_pairs
    timestamp DATETIME NOT NULL,                 -- Candle timestamp
    open DECIMAL(18,8) NOT NULL,
    high DECIMAL(18,8) NOT NULL,
    low DECIMAL(18,8) NOT NULL,
    close DECIMAL(18,8) NOT NULL,
    volume DECIMAL(18,8) NOT NULL,
    data_source VARCHAR(50) NOT NULL DEFAULT 'coinbase',
    created_at DATETIME NOT NULL DEFAULT GETDATE(),
    
    -- Composite unique constraint prevents duplicates
    CONSTRAINT uq_market_price_pair_timestamp UNIQUE (trading_pair_id, timestamp)
);

-- Indexes for query performance
CREATE INDEX ix_market_prices_pair_time ON crypto.market_prices (trading_pair_id, timestamp);
CREATE INDEX ix_market_prices_timestamp_desc ON crypto.market_prices (timestamp DESC);
```

**Design Rationale**:
- **Primary Key**: Auto-increment `id` for internal references
- **Composite Unique Key**: `(trading_pair_id, timestamp)` prevents duplicate candles
- **Indexes**: Optimized for time-series queries

This design allows:
- ✅ Efficient lookups by ID
- ✅ Duplicate prevention via unique constraint
- ✅ Fast time-range queries
- ✅ Automatic IntegrityError handling in ingestion code

## Common Operations

### 1. Create a New Migration

```bash
# Generate migration from model changes
alembic revision --autogenerate -m "Add new column to market_prices"

# Create empty migration for manual changes
alembic revision -m "Custom database changes"
```

### 2. Review Migration Before Applying

```bash
# Check current database version
alembic current

# View migration SQL without applying
alembic upgrade head --sql

# View pending migrations
alembic history
```

### 3. Apply Migrations

```bash
# Upgrade to latest version
alembic upgrade head

# Upgrade by one version
alembic upgrade +1

# Upgrade to specific revision
alembic upgrade <revision_id>
```

### 4. Rollback Migrations

```bash
# Downgrade by one version
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade <revision_id>

# Downgrade to base (empty database)
alembic downgrade base
```

### 5. Drop and Recreate Schema

When major changes require a clean slate:

```bash
# Step 1: Drop all data (CAUTION!)
python scripts/db_reset.py

# Step 2: Run all migrations
alembic upgrade head

# Step 3: Seed initial data
python scripts/seed_database.py
```

## Example: Modifying Market Prices Table

### Scenario: Change Column Type

If you need to change a column (e.g., increase precision):

**Step 1**: Update the model in `src/cryptoquant/database/models.py`

```python
class MarketPrice(Base):
    # Change from Numeric(18, 8) to Numeric(24, 12)
    open = Column(Numeric(24, 12), nullable=False)
    high = Column(Numeric(24, 12), nullable=False)
    low = Column(Numeric(24, 12), nullable=False)
    close = Column(Numeric(24, 12), nullable=False)
    volume = Column(Numeric(24, 12), nullable=False)
```

**Step 2**: Generate migration

```bash
alembic revision --autogenerate -m "Increase precision for OHLCV columns"
```

**Step 3**: Review migration file

```bash
# Open: alembic/versions/006_increase_precision.py
# Verify the upgrade() and downgrade() functions
```

**Step 4**: Test on development

```bash
# Apply migration
alembic upgrade head

# Test ingestion
python scripts/collect_historic_data.py --days 7 --product-id BTC-USD

# If issues arise, rollback
alembic downgrade -1
```

**Step 5**: Deploy to production

```bash
# On production server
git pull origin main
alembic upgrade head
```

## Example: Drop and Recreate Table

If the schema change is too complex for incremental migration:

**Step 1**: Backup existing data (if needed)

```sql
-- Export to CSV
SELECT * FROM crypto.market_prices 
ORDER BY timestamp
-- Save results

-- Or create backup table
SELECT * INTO crypto.market_prices_backup
FROM crypto.market_prices;
```

**Step 2**: Create drop migration

```bash
alembic revision -m "Drop and recreate market_prices"
```

**Step 3**: Edit migration file

```python
# alembic/versions/006_recreate_market_prices.py

def upgrade():
    # Drop table
    op.drop_table('market_prices', schema='crypto')
    
    # Recreate with new structure
    op.create_table(
        'market_prices',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('trading_pair_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('open', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('high', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('low', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('close', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('volume', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('data_source', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['trading_pair_id'], ['crypto.trading_pairs.id']),
        sa.UniqueConstraint('trading_pair_id', 'timestamp', name='uq_market_price_pair_timestamp'),
        schema='crypto'
    )
    
    # Recreate indexes
    op.create_index('ix_market_prices_pair_time', 'market_prices', ['trading_pair_id', 'timestamp'], schema='crypto')
    op.create_index('ix_market_prices_timestamp_desc', 'market_prices', ['timestamp'], schema='crypto')

def downgrade():
    op.drop_table('market_prices', schema='crypto')
```

**Step 4**: Apply migration

```bash
alembic upgrade head
```

**Step 5**: Re-ingest data

```bash
# Fresh 3-year historic load
python scripts/collect_historic_data.py --days 1095 --granularity hourly
```

## Troubleshooting

### "Target database is not up to date"

```bash
# Check current version
alembic current

# Stamp database to specific version (if migrations got out of sync)
alembic stamp head
```

### "Can't locate revision"

```bash
# Clear alembic version table and re-stamp
# WARNING: Only do this if you're certain about your schema state
alembic stamp base
alembic upgrade head
```

### Migration Fails Midway

```bash
# Check database state
alembic current

# Manual cleanup if needed
# Connect to database and inspect tables

# Downgrade to last known good state
alembic downgrade -1

# Fix migration file, then retry
alembic upgrade head
```

## Best Practices

1. **Always Review**: Check generated migrations before applying
2. **Test First**: Apply migrations to dev/test environment before production
3. **Backup**: Export data before destructive operations
4. **Version Control**: Commit migration files to git
5. **Descriptive Names**: Use clear migration messages
6. **Document**: Add comments in migration files for complex changes

## Quick Reference

| Task | Command |
|------|---------|
| Create migration | `alembic revision --autogenerate -m "message"` |
| Apply all | `alembic upgrade head` |
| Apply one | `alembic upgrade +1` |
| Rollback one | `alembic downgrade -1` |
| Current version | `alembic current` |
| Migration history | `alembic history` |
| Generate SQL | `alembic upgrade head --sql` |
| Reset database | `python scripts/db_reset.py` |

## Related Documentation

- [Database Design](DATABASE_DESIGN.md)
- [Database Setup Guide](DATABASE_SETUP_GUIDE.md)
- [Historic Ingestion](HISTORIC_INGESTION.md)
- [Ingestion Resume Guide](INGESTION_RESUME_GUIDE.md)

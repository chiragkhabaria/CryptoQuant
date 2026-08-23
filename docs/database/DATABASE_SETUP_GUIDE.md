# Database Setup and Migration Guide

This document explains the database setup process for the CryptoQuant platform.

## Overview

The CryptoQuant platform uses **Azure SQL Server** (or any SQL Server) with a dedicated **`crypto` schema** to organize all cryptocurrency-related tables. This schema-based approach allows the same database to host multiple domains (e.g., crypto, finance, stocks) without naming conflicts.

## Database Structure

### Schema: `crypto`

All cryptocurrency tables are created under the `crypto` schema:
- `crypto.assets` - Cryptocurrency assets (BTC, ETH, USD, etc.)
- `crypto.trading_pairs` - Trading pairs (BTC-USD, ETH-USD, etc.)
- `crypto.market_prices` - Historical OHLCV price data

### Key Design Decisions

1. **Schema Isolation**: Using `crypto` schema allows future expansion to other domains (e.g., `finance`, `stocks`)
2. **Normalization**: Assets are normalized to prevent duplication (BTC, ETH stored once)
3. **API Alignment**: `trading_pairs` table columns match Coinbase Product API for seamless ingestion
4. **Indexing**: Strategic indexes on frequently queried columns (symbol, timestamp, trading_pair_id)

## Table Schemas

### crypto.assets

Stores individual cryptocurrency and fiat assets.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| symbol | VARCHAR(20) | Asset symbol (e.g., 'BTC', 'USD') - UNIQUE |
| name | VARCHAR(100) | Full asset name (e.g., 'Bitcoin') |
| display_symbol | VARCHAR(20) | Display symbol for UI |
| asset_type | VARCHAR(20) | Type: 'cryptocurrency', 'fiat' |
| decimals | INTEGER | Decimal precision (default: 8) |
| active | BOOLEAN | Whether asset is actively traded |
| created_at | DATETIME | Record creation timestamp |
| updated_at | DATETIME | Last update timestamp |

**Indexes:**
- `ix_crypto_assets_symbol` (UNIQUE)
- `ix_crypto_assets_active`

### crypto.trading_pairs

Stores tradeable pairs with Coinbase Product API fields.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| base_asset_id | INTEGER | FK to crypto.assets (base currency) |
| quote_asset_id | INTEGER | FK to crypto.assets (quote currency) |
| symbol | VARCHAR(20) | Trading pair symbol (e.g., 'BTC-USD') - UNIQUE |
| status | VARCHAR(20) | Trading status: 'online', 'offline', 'delisted' |
| trading_disabled | BOOLEAN | Whether trading is currently disabled |
| active | BOOLEAN | Whether pair is actively tracked |
| base_increment | NUMERIC(18,8) | Minimum order size increment |
| quote_increment | NUMERIC(18,8) | Minimum price increment (tick size) |
| base_min_size | NUMERIC(18,8) | Minimum order quantity |
| base_max_size | NUMERIC(18,8) | Maximum order quantity |
| quote_min_size | NUMERIC(18,8) | Minimum order value in quote currency |
| quote_max_size | NUMERIC(18,8) | Maximum order value in quote currency |
| created_at | DATETIME | Record creation timestamp |
| updated_at | DATETIME | Last update timestamp |

**Indexes:**
- `ix_crypto_trading_pairs_symbol` (UNIQUE)
- `ix_crypto_trading_pairs_active`

### crypto.tracked_pairs

Controls which trading pairs to actively monitor for data collection.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| product_id | VARCHAR(50) | Trading pair identifier (e.g., 'BTC-USD') - UNIQUE |
| symbol | VARCHAR(20) | Display symbol |
| is_tracking_active | BOOLEAN | Enable/disable tracking (1=active, 0=inactive) |
| created_at | DATETIME | Record creation timestamp |
| modified_at | DATETIME | Last modification timestamp (auto-updated) |

**Indexes:**
- `ix_crypto_tracked_pairs_product_id` (UNIQUE)
- `ix_crypto_tracked_pairs_symbol`
- `ix_crypto_tracked_pairs_is_tracking_active`

**Purpose**: Selective monitoring - only pairs with `is_tracking_active=1` are processed by historic/live data ingestion scripts.

### crypto.market_prices

Stores historical OHLCV (candlestick) price data.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| trading_pair_id | INTEGER | FK to crypto.trading_pairs |
| timestamp | DATETIME | Candle start time |
| open | NUMERIC(18,8) | Opening price |
| high | NUMERIC(18,8) | Highest price in period |
| low | NUMERIC(18,8) | Lowest price in period |
| close | NUMERIC(18,8) | Closing price |
| volume | NUMERIC(18,8) | Trading volume |
| data_source | VARCHAR(50) | Data source (e.g., 'coinbase') |
| created_at | DATETIME | Record creation timestamp |

**Constraints:**
- `uq_market_price_pair_timestamp` - Prevents duplicate candles for same pair/time

**Indexes:**
- `ix_crypto_market_prices_trading_pair_id`
- `ix_crypto_market_prices_pair_time` (composite: trading_pair_id, timestamp)
- `ix_crypto_market_prices_timestamp_desc`

## Database Setup Process

### Prerequisites

1. **Azure SQL Server** (or SQL Server) instance running
2. **Database created**: `fin-market-db` (or your database name)
3. **Credentials**: Admin user with schema creation permissions
4. **Connection string** in `.env` file:
   ```
   DATABASE_URL=mssql+pyodbc://username:password@server.database.windows.net:1433/database?driver=ODBC+Driver+18+for+SQL+Server
   ```

### Step 1: Install Dependencies

Ensure you have the required Python packages:

```bash
poetry install
# Or if using pip:
pip install sqlalchemy alembic pyodbc python-dotenv
```

### Step 2: Run Database Migration

The migration will:
1. Create the `crypto` schema
2. Create all tables with proper structure
3. Set up indexes and foreign keys
4. Clean up any old tables from `dbo` schema (if they exist)

**Using Alembic:**

```bash
# Check current migration status
alembic current

# Run the migration to create crypto schema
alembic upgrade head
```

**Using the db_migrate script:**

```bash
python scripts/db_migrate.py
```

### Step 3: Verify Schema Creation

Connect to your database and verify:

```sql
-- Check schema exists
SELECT * FROM sys.schemas WHERE name = 'crypto';

-- List all tables in crypto schema
SELECT TABLE_NAME 
FROM INFORMATION_SCHEMA.TABLES 
WHERE TABLE_SCHEMA = 'crypto';

-- Verify table structure
SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'crypto' AND TABLE_NAME = 'assets';
```

### Step 4: Populate Initial Data

After schema is created, populate with initial data:

**Phase I: Asset Data**
```bash
# Populate assets from Coinbase API
# Execute all cells in: tests/integration/test_data_ingestion.ipynb
```

**Phase II: Trading Pairs (REQUIRED before historic data collection)**
```bash
# Populate trading pairs from Coinbase API
# Execute all cells in: tests/integration/populate_trading_pairs.ipynb
```

This notebook will:
- Fetch all 912 products from Coinbase API
| 003 | Add product_id to assets table | 2026-08-08 |
| 005 | Create tracked_pairs table | 2026-08-11 |
- Create any missing assets (base/quote currencies)
- Insert trading pairs with order constraints
- Verify tracked pairs are present

**Verification:**
```sql
SELECT COUNT(*) FROM crypto.assets;           -- Should be ~400+
SELECT COUNT(*) FROM crypto.trading_pairs;    -- Should be ~912
SELECT COUNT(*) FROM crypto.tracked_pairs;    -- Should be 4 initially
```

## Migration History

| Revision | Description | Date |
|----------|-------------|------|
| 001 | Initial schema (dbo) | 2026-08-05 |
| 002 | Add crypto schema, enhanced columns | 2026-08-07 |

## Rollback Instructions

If you need to rollback the migration:

```bash
# Rollback to previous version
alembic downgrade -1

# Or rollback to specific version
alembic downgrade 001
```

**Warning**: Rollback will **delete all data** in the crypto schema.

## Troubleshooting

### Connection Issues

**Error**: "Login failed for user"
- **Solution**: Verify credentials in `.env` file
- Check firewall rules allow your IP address

**Error**: "Driver not found"
- **Solution**: Install ODBC Driver 18 for SQL Server
  - Windows: Download from Microsoft
  - Linux: `sudo apt-get install unixodbc-dev`

### Schema Issues

**Error**: "Schema 'crypto' already exists"
- **Solution**: Either drop the existing schema or skip migration:
  ```sql
  DROP SCHEMA crypto;
  ```

**Error**: "Cannot drop schema 'crypto' because it is being referenced"
- **Solution**: Drop tables first:
  ```sql
  DROP TABLE crypto.market_prices;
  DROP TABLE crypto.trading_pairs;
  DROP TABLE crypto.assets;
  DROP SCHEMA crypto;
  ```

### Permission Issues

**Error**: "User does not have permission to create schema"
- **Solution**: Grant schema creation permissions:
  ```sql
  GRANT CREATE SCHEMA TO [your-user];
  ```

## Best Practices

1. **Always backup** before running migrations on production
2. **Test migrations** on a dev/staging database first
3. **Review migration scripts** before running
4. **Monitor performance** after adding indexes
5. **Use connection pooling** for production workloads
6. **Set appropriate timeouts** for large data operations

## Connection String Format

### Azure SQL Server

```
DATABASE_URL=mssql+pyodbc://username:password@server.database.windows.net:1433/database?driver=ODBC+Driver+18+for+SQL+Server
```

### SQL Server (Windows Authentication)

```
DATABASE_URL=mssql+pyodbc://server/database?driver=ODBC+Driver+18+for+SQL+Server&trusted_connection=yes
```

### SQLite (Local Development)

```
DATABASE_URL=sqlite:///./cryptoquant_dev.db
```

## Phase II: Historic Data Collection

After initial database setup and trading pair population, load historical market data:

### 1. Initial 3-Year Daily Load

Load 3 years of daily OHLCV data for tracked pairs:

```powershell
python scripts/collect_historic_data.py --granularity daily --days 1095
```

**Expected results:**
- Processes 4 tracked pairs (BTC-USD, ETH-USD, XRP-USD, SOL-USD)
- ~1095 daily candles per pair
- Total: ~4,380 records

### 2. Transition to Hourly Data (Future)

After initial analysis, load hourly data for refined strategies:

```powershell
# Load last 90 days of hourly data
python scripts/collect_historic_data.py --granularity hourly --days 90
```

### 3. Daily Updates

Keep data current with automated daily updates:

```powershell
# Fetch last 2 days (catches any gaps)
python scripts/collect_historic_data.py --granularity daily --days 2
```

**For detailed historic ingestion instructions, see:** [HISTORIC_INGESTION.md](HISTORIC_INGESTION.md)

## Next Steps

After database setup and historic data load:

1. ✅ Run ingestion notebook to populate assets from Coinbase
2. ✅ Run trading pairs notebook to populate all 912 pairs
3. ✅ Run historic data collection for 3-year daily data
4. ⏳ Set up scheduled daily updates for market prices
5. ⏳ Configure monitoring and alerting
6. ⏳ Implement backup strategy

## Support

For issues or questions:
- Check Alembic logs: `alembic.log`
- Review database connection settings
- Verify SQL Server version compatibility
- Consult SQLAlchemy documentation for dialect-specific issues

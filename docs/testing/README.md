# Testing Documentation

Welcome to the CryptoQuant Testing Documentation. This directory contains comprehensive guides for testing all aspects of the platform.

## 📚 Documentation Index

### Getting Started
- **[INGESTION_GETTING_STARTED.md](INGESTION_GETTING_STARTED.md)** - Quick start guide for ingestion testing (3-step setup)
- **[INGESTION_QUICK_REFERENCE.md](INGESTION_QUICK_REFERENCE.md)** - Command cheatsheet and quick reference

### Comprehensive Guides
- **[INGESTION_TESTING.md](INGESTION_TESTING.md)** - Complete ingestion testing guide (500+ lines)
- **[AZURE_SQL_TROUBLESHOOTING.md](AZURE_SQL_TROUBLESHOOTING.md)** - Azure SQL connection troubleshooting

### Test Scripts
All test scripts are located in `tests/` directory:
- `tests/ingestion/test_candle_ingestion.py` - Main ingestion test script
- `tests/ingestion/test_db_connection.py` - Database connection test utility

---

## 🚀 Quick Start

### Step 1: Setup Azure SQL Firewall

**Your IP must be whitelisted before running tests!**

```powershell
# Automated (recommended)
.\scripts\update_azure_firewall.ps1 -ResourceGroup "YourResourceGroup"

# Wait 2-5 minutes, then test
python tests/ingestion/test_db_connection.py
```

### Step 2: Run Ingestion Tests

```powershell
# Test with a single pair first (recommended)
python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD

# If successful, test all pairs
python tests/ingestion/test_candle_ingestion.py
```

### Step 3: Review Results

- Check console output for pass/fail status
- Review detailed logs in `logs/test_candle_ingestion_*.log`
- Verify data in database

---

## 📖 Testing Categories

### 1. Candle Ingestion Testing

Tests the complete pipeline for fetching and storing OHLCV candle data.

**What it tests**:
- Historical data ingestion (30 days until yesterday)
- Incremental data ingestion (yesterday to today)
- Data integrity validation
- API connectivity
- Database operations
- Error handling

**Documentation**:
- [INGESTION_TESTING.md](INGESTION_TESTING.md) - Comprehensive guide
- [INGESTION_QUICK_REFERENCE.md](INGESTION_QUICK_REFERENCE.md) - Quick commands

**Test Scripts**:
- `tests/ingestion/test_candle_ingestion.py` - Main test suite
- `tests/ingestion/test_db_connection.py` - Connection verification

**Common Commands**:
```powershell
# Run all ingestion tests
python tests/ingestion/test_candle_ingestion.py

# Test specific pair
python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD

# Test only historical ingestion
python tests/ingestion/test_candle_ingestion.py --test historical

# Test only incremental ingestion
python tests/ingestion/test_candle_ingestion.py --test incremental
```

---

## 🔧 Troubleshooting

### Connection Issues

**Symptom**: Tests fail with "Cannot open server" or "Login timeout expired"

**Solution**: Your IP needs to be whitelisted in Azure SQL firewall.

```powershell
# 1. Run connection test to diagnose
python tests/ingestion/test_db_connection.py

# 2. Fix firewall (automated)
.\scripts\update_azure_firewall.ps1 -ResourceGroup "YourResourceGroup"

# 3. Wait 2-5 minutes and retry
python tests/ingestion/test_db_connection.py
```

**Detailed Guide**: [AZURE_SQL_TROUBLESHOOTING.md](AZURE_SQL_TROUBLESHOOTING.md)

### Common Issues

| Issue | Quick Fix |
|-------|-----------|
| Firewall error | Run `.\scripts\update_azure_firewall.ps1` |
| Connection timeout | Check firewall, increase timeout in DATABASE_URL |
| No tracked pairs | Run `python scripts/seed_database.py` |
| API auth error | Verify Coinbase credentials in `.env` |
| Test hangs | Try single pair: `--product-id BTC-USD` |

---

## 📋 Prerequisites

Before running any tests:

1. **Database Setup**
   ```powershell
   python scripts/db_init.py
   python scripts/db_migrate.py
   python scripts/seed_database.py
   ```

2. **Azure SQL Firewall**
   ```powershell
   .\scripts\update_azure_firewall.ps1 -ResourceGroup "YourResourceGroup"
   # Wait 2-5 minutes
   python tests/ingestion/test_db_connection.py
   ```

3. **Environment Variables** (`.env` file)
   ```
   DATABASE_URL=mssql+pyodbc://user:password@server.database.windows.net/database?driver=ODBC+Driver+18+for+SQL+Server
   COINBASE_API_KEY=your_api_key
   COINBASE_API_SECRET=your_api_secret
   ```

4. **Virtual Environment**
   ```powershell
   .venv\Scripts\activate
   ```

---

## 📂 File Structure

```
docs/testing/
├── README.md                           # This file - main index
├── INGESTION_TESTING.md                # Comprehensive ingestion test guide
├── INGESTION_QUICK_REFERENCE.md        # Quick command reference
├── INGESTION_GETTING_STARTED.md        # Quick start (3 steps)
└── AZURE_SQL_TROUBLESHOOTING.md        # Azure SQL connection troubleshooting

tests/ingestion/
├── __init__.py
├── test_candle_ingestion.py            # Main ingestion test script
├── test_db_connection.py               # Database connection test utility
└── README.md                           # Test directory README

scripts/
└── update_azure_firewall.ps1           # Automated firewall rule updater

logs/
└── test_candle_ingestion_*.log         # Test execution logs
```

---

## 🎯 Test Workflows

### Daily Testing Workflow

```powershell
# 1. Test incremental ingestion (quick)
python tests/ingestion/test_candle_ingestion.py --test incremental

# 2. Review logs if there are issues
Get-Content logs\test_candle_ingestion_*.log -Tail 50
```

### Weekly Testing Workflow

```powershell
# 1. Run full test suite
python tests/ingestion/test_candle_ingestion.py --test all

# 2. Test with different granularities
python tests/ingestion/test_candle_ingestion.py --granularity hourly

# 3. Review all logs
dir logs\test_candle_ingestion_*.log | Sort-Object LastWriteTime -Descending | Select-Object -First 5
```

### Pre-Deployment Testing

```powershell
# 1. Test database connection
python tests/ingestion/test_db_connection.py

# 2. Run full ingestion tests
python tests/ingestion/test_candle_ingestion.py

# 3. Test specific pairs
python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD
python tests/ingestion/test_candle_ingestion.py --product-id ETH-USD

# 4. Verify all tests pass
# Check exit codes and logs
```

---

## 🎓 Best Practices

1. **Always test connection first**
   ```powershell
   python tests/ingestion/test_db_connection.py
   ```

2. **Start with single pair**
   ```powershell
   python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD
   ```

3. **Review logs after tests**
   ```powershell
   # Get latest log file
   $latestLog = Get-ChildItem logs\test_candle_ingestion_*.log | Sort-Object LastWriteTime -Descending | Select-Object -First 1
   Get-Content $latestLog -Tail 100
   ```

4. **Keep logs organized**
   - Logs are automatically timestamped
   - Old logs are preserved for historical analysis
   - Logs are excluded from Git (in `.gitignore`)

5. **Test after changes**
   - After database schema changes
   - After API integration changes
   - Before deploying to production

---

## 🔮 Future Testing Modules

Following the same pattern as candle ingestion, future test modules will cover:

### Planned Test Categories

1. **Indicator Generation Tests** (`tests/indicators/`)
   - Test technical indicator calculations
   - Validate indicator values against known datasets
   - Test performance with large datasets

2. **Strategy Backtesting Tests** (`tests/backtesting/`)
   - Test strategy logic with historical data
   - Validate P&L calculations
   - Test risk management rules

3. **Execution Tests** (`tests/execution/`)
   - Test order placement (paper trading)
   - Validate order routing
   - Test error handling for rejected orders

4. **Portfolio Tests** (`tests/portfolio/`)
   - Test position tracking
   - Validate P&L calculations
   - Test rebalancing logic

5. **Scheduler Tests** (`tests/scheduling/`)
   - Test job scheduling and execution
   - Validate error recovery
   - Test concurrent job handling

Each module will have:
- Comprehensive test script
- Detailed documentation
- Quick reference guide
- Troubleshooting section

---

## 📞 Getting Help

### Documentation Resources

- **Ingestion Testing**: [INGESTION_TESTING.md](INGESTION_TESTING.md)
- **Azure SQL Issues**: [AZURE_SQL_TROUBLESHOOTING.md](AZURE_SQL_TROUBLESHOOTING.md)
- **Quick Commands**: [INGESTION_QUICK_REFERENCE.md](INGESTION_QUICK_REFERENCE.md)

### Diagnostic Tools

```powershell
# Test database connection
python tests/ingestion/test_db_connection.py

# Check logs
dir logs\test_candle_ingestion_*.log | Sort-Object LastWriteTime -Descending

# View latest log
Get-Content (Get-ChildItem logs\test_candle_ingestion_*.log | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName
```

### Common Commands

```powershell
# Fix firewall
.\scripts\update_azure_firewall.ps1 -ResourceGroup "YourResourceGroup"

# Test connection
python tests/ingestion/test_db_connection.py

# Run tests
python tests/ingestion/test_candle_ingestion.py

# Get help
python tests/ingestion/test_candle_ingestion.py --help
```

---

## ✅ Quick Checklist

Before running tests, ensure:

- [ ] Virtual environment activated (`.venv\Scripts\activate`)
- [ ] Database initialized (`python scripts/db_init.py`)
- [ ] Migrations applied (`python scripts/db_migrate.py`)
- [ ] Tracked pairs seeded (`python scripts/seed_database.py`)
- [ ] `.env` file configured with valid credentials
- [ ] **Azure SQL firewall rule added for your IP**
- [ ] Connection tested (`python tests/ingestion/test_db_connection.py`)

Then run:
```powershell
python tests/ingestion/test_candle_ingestion.py
```

---

## 📊 Summary

The testing infrastructure provides:

- ✅ **Comprehensive Test Coverage** - Historical and incremental ingestion
- ✅ **Automated Validation** - Data integrity checks built-in
- ✅ **Detailed Logging** - All operations logged for debugging
- ✅ **Clear Error Messages** - Helpful troubleshooting guidance
- ✅ **Flexible Configuration** - Test specific pairs or granularities
- ✅ **Azure SQL Tools** - Connection testing and firewall management
- ✅ **Extensive Documentation** - 1000+ lines of guides and examples

**Start Testing**: [INGESTION_GETTING_STARTED.md](INGESTION_GETTING_STARTED.md)

**Need Help**: [AZURE_SQL_TROUBLESHOOTING.md](AZURE_SQL_TROUBLESHOOTING.md)

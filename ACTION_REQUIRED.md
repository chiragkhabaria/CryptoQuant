# Action Required: Azure SQL Firewall Setup

## 🔥 Current Issue

**The ingestion tests are failing because your IP address is not whitelisted in Azure SQL Server firewall.**

**Your IP Address**: `174.198.202.169`  
**Server**: `fin-market-sqlserver.database.windows.net`  
**Database**: `fin-market-db`

---

## ✅ Solution (Choose One)

### Option 1: Automated (Recommended) ⚡

Run the PowerShell script I created:

```powershell
# Replace "YourResourceGroup" with your actual Azure resource group name
.\scripts\update_azure_firewall.ps1 -ResourceGroup "YourResourceGroup"
```

**What it does**:
- Detects your current IP automatically
- Adds it to Azure SQL Server firewall rules
- Provides clear status and error messages

**Wait Time**: 2-5 minutes for changes to take effect

### Option 2: Azure Portal (Manual) 🌐

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to: **SQL Server** → `fin-market-sqlserver`
3. Click: **Networking** (in left sidebar)
4. Click: **+ Add client IP** button
5. Click: **Save**
6. **Wait 2-5 minutes** for changes to propagate

### Option 3: Azure CLI (Manual) 💻

```powershell
# Get your IP
$myIP = (Invoke-WebRequest -Uri "https://api.ipify.org").Content
Write-Host "Your IP: $myIP"

# Add firewall rule (replace resource group name)
az sql server firewall-rule create `
  --resource-group "YourResourceGroup" `
  --server fin-market-sqlserver `
  --name LocalDevelopmentMachine `
  --start-ip-address $myIP `
  --end-ip-address $myIP
```

---

## 🧪 Test Connection

After whitelisting your IP and waiting 2-5 minutes:

```powershell
# Step 1: Test database connection
python tests/ingestion/test_db_connection.py
```

**Expected Output**:
```
✅ DATABASE CONNECTION TEST PASSED

Your database connection is working correctly!
You can now run the ingestion tests:
  python tests/ingestion/test_candle_ingestion.py
```

---

## 🚀 Run Ingestion Tests

Once connection test passes:

```powershell
# Step 2: Run ingestion tests (start with single pair)
python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD

# Step 3: If successful, run all tests
python tests/ingestion/test_candle_ingestion.py
```

---

## 📚 What Was Fixed & Created

### 1. ✅ Logs Already in .gitignore
```
# Logs  
logs/*
!logs/.gitkeep
*.log
```
Your logs are already excluded from Git. ✅

### 2. ✅ Documentation Moved to docs/testing/

All testing documentation has been centralized in `docs/testing/`:

```
docs/testing/
├── README.md                         # Main testing index (comprehensive)
├── INGESTION_TESTING.md              # Complete ingestion guide (500+ lines)
├── INGESTION_QUICK_REFERENCE.md      # Command cheatsheet
├── INGESTION_GETTING_STARTED.md      # Quick 3-step start guide
└── AZURE_SQL_TROUBLESHOOTING.md      # Detailed Azure SQL troubleshooting
```

### 3. ✅ Database Connection Test Utility Created

**File**: `tests/ingestion/test_db_connection.py`

**Features**:
- Tests database connectivity
- Identifies specific connection issues
- Provides context-specific troubleshooting
- Clear error messages with solutions

**Usage**:
```powershell
python tests/ingestion/test_db_connection.py
```

### 4. ✅ Automated Firewall Rule Updater Created

**File**: `scripts/update_azure_firewall.ps1`

**Features**:
- Automatically detects your current IP
- Creates or updates Azure SQL firewall rules
- Validates Azure CLI and login status
- Provides clear success/error messages

**Usage**:
```powershell
.\scripts\update_azure_firewall.ps1 -ResourceGroup "YourResourceGroup"
```

### 5. ✅ Improved Test Error Handling

**File**: `tests/ingestion/test_candle_ingestion.py`

**Improvements**:
- Better connection error detection
- Context-specific error messages
- Clear guidance for firewall issues
- References to troubleshooting documentation

### 6. ✅ Comprehensive Documentation

Created 1500+ lines of documentation:
- Azure SQL troubleshooting guide
- Connection testing guide
- Firewall automation guide
- Test suite documentation

---

## 🎯 Next Steps (In Order)

### Step 1: Whitelist Your IP (Choose one method above)
```powershell
# Automated (easiest)
.\scripts\update_azure_firewall.ps1 -ResourceGroup "YourResourceGroup"

# OR use Azure Portal manually
```

### Step 2: Wait 2-5 Minutes
⏱️ Azure needs time to propagate the firewall rule changes.

### Step 3: Test Connection
```powershell
python tests/ingestion/test_db_connection.py
```

### Step 4: Run Ingestion Tests
```powershell
# Single pair test
python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD

# Full test
python tests/ingestion/test_candle_ingestion.py
```

### Step 5: Review Results
- Check console output for ✅ PASSED
- Review logs in `logs/test_candle_ingestion_*.log`
- Verify data in database

---

## 📖 Documentation Quick Links

| Document | Purpose |
|----------|---------|
| [docs/testing/README.md](../docs/testing/README.md) | Main testing documentation index |
| [docs/testing/AZURE_SQL_TROUBLESHOOTING.md](../docs/testing/AZURE_SQL_TROUBLESHOOTING.md) | Detailed Azure SQL troubleshooting |
| [docs/testing/INGESTION_TESTING.md](../docs/testing/INGESTION_TESTING.md) | Complete ingestion testing guide |
| [docs/testing/INGESTION_QUICK_REFERENCE.md](../docs/testing/INGESTION_QUICK_REFERENCE.md) | Quick command reference |
| [docs/testing/INGESTION_GETTING_STARTED.md](../docs/testing/INGESTION_GETTING_STARTED.md) | 3-step getting started guide |

---

## 🔍 Troubleshooting

### If connection test still fails after whitelisting:

1. **Wait longer** - Sometimes takes up to 5 minutes
2. **Verify rule was created**:
   ```powershell
   az sql server firewall-rule list --resource-group "YourResourceGroup" --server fin-market-sqlserver --output table
   ```
3. **Check if your IP changed**:
   ```powershell
   $myIP = (Invoke-WebRequest -Uri "https://api.ipify.org").Content
   Write-Host "Current IP: $myIP"
   ```
4. **Re-run the firewall script** if IP changed
5. **See detailed guide**: [docs/testing/AZURE_SQL_TROUBLESHOOTING.md](../docs/testing/AZURE_SQL_TROUBLESHOOTING.md)

---

## ✅ Summary

**Issue**: Azure SQL firewall blocking your IP (`174.198.202.169`)

**Solution**: Whitelist your IP using one of the methods above

**Then**: Test connection and run ingestion tests

**Documentation**: All testing docs now in `docs/testing/` directory

**Logs**: Already in `.gitignore` ✅

**Ready for**: Production deployment after tests pass ✅

---

## 🚀 Quick Command Summary

```powershell
# 1. Fix firewall (choose your resource group name)
.\scripts\update_azure_firewall.ps1 -ResourceGroup "YourResourceGroup"

# 2. Wait 2-5 minutes, then test connection
python tests/ingestion/test_db_connection.py

# 3. Run tests
python tests/ingestion/test_candle_ingestion.py --product-id BTC-USD

# 4. Review logs
Get-Content (Get-ChildItem logs\test_candle_ingestion_*.log | Sort-Object LastWriteTime -Descending | Select-Object -First 1).FullName -Tail 50
```

---

**Once tests pass, you're ready for deployment! 🎉**

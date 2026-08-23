# Azure SQL Database Connection Troubleshooting

## Common Connection Issues and Solutions

### Issue 1: Firewall Rule Error

**Error Message**:
```
Cannot open server 'devsqlserver001' requested by the login. 
Client with IP address 'X.X.X.X' is not allowed to access the server.
```

**Cause**: Your IP address is not whitelisted in Azure SQL Server firewall rules.

**Solutions**:

#### Option 1: Azure Portal (Recommended)
1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your SQL Server: `devsqlserver001`
3. Click **"Networking"** or **"Firewalls and virtual networks"**
4. Add your client IP address:
   - Click **"+ Add client IP"** (adds your current IP automatically)
   - Or manually add IP range
5. Click **"Save"**
6. Wait 2-5 minutes for changes to propagate

#### Option 2: Azure CLI
```powershell
# Get your current IP
$myIP = (Invoke-WebRequest -Uri "https://api.ipify.org").Content

# Add firewall rule
az sql server firewall-rule create `
  --resource-group YourResourceGroup `
  --server devsqlserver001 `
  --name MyDevMachine `
  --start-ip-address $myIP `
  --end-ip-address $myIP
```

#### Option 3: T-SQL (If you have master access)
```sql
-- Connect to master database
EXEC sp_set_firewall_rule 
  @name = N'MyDevMachine',
  @start_ip_address = '123.456.789.012', 
  @end_ip_address = '123.456.789.012'
```

---

### Issue 2: Connection Timeout

**Error Message**:
```
TCP Provider: Timeout error [258]
Login timeout expired
```

**Possible Causes**:
1. Firewall blocking connection
2. Network latency
3. Azure SQL server is busy
4. VPN or proxy interference

**Solutions**:

1. **Check Firewall**: See Issue 1 above

2. **Increase Connection Timeout**: Update your `.env` file:
   ```
   DATABASE_URL=mssql+pyodbc://user:password@server.database.windows.net/dbname?driver=ODBC+Driver+18+for+SQL+Server&Timeout=60
   ```
   Add `&Timeout=60` to increase timeout to 60 seconds.

3. **Test Basic Connectivity**:
   ```powershell
   # Test if server is reachable
   Test-NetConnection -ComputerName devsqlserver001.database.windows.net -Port 1433
   ```

4. **Disable VPN temporarily** to test if it's causing issues

5. **Use Azure SQL connection test utility**:
   ```powershell
   python tests/ingestion/test_db_connection.py
   ```

---

### Issue 3: Authentication Failed

**Error Message**:
```
Login failed for user 'username'
```

**Solutions**:

1. **Verify Credentials**: Check your `.env` file
   ```
   DATABASE_URL=mssql+pyodbc://username:password@server/database?driver=...
   ```

2. **Password Special Characters**: URL-encode special characters in password:
   - `@` becomes `%40`
   - `#` becomes `%23`
   - `&` becomes `%26`
   - Example: `P@ssw0rd!` becomes `P%40ssw0rd%21`

3. **Test Connection Manually**:
   ```powershell
   sqlcmd -S devsqlserver001.database.windows.net -d fin-market-db -U your_username -P your_password
   ```

---

### Issue 4: SSL/TLS Certificate Error

**Error Message**:
```
SSL Provider: The certificate chain was issued by an authority that is not trusted
```

**Solution**: Add `TrustServerCertificate=yes` to connection string:
```
DATABASE_URL=mssql+pyodbc://user:password@server/database?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes
```

---

## Testing Database Connection

### Quick Connection Test

Create a simple test script to verify database connectivity:

```python
# test_db_connection.py
from cryptoquant.database.session import get_engine
from sqlalchemy import text

try:
    engine = get_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1 AS test"))
        print("✅ Database connection successful!")
        print(f"Database: {engine.url.database}")
except Exception as e:
    print(f"❌ Database connection failed: {e}")
```

Run it:
```powershell
python test_db_connection.py
```

---

## Azure SQL Firewall Setup Checklist

Before running ingestion tests, ensure:

- [ ] Your current IP is whitelisted in Azure SQL firewall
- [ ] Port 1433 is not blocked by local firewall
- [ ] Connection string in `.env` is correct
- [ ] Driver (ODBC Driver 18 for SQL Server) is installed
- [ ] Network connectivity to Azure is working
- [ ] Credentials are valid and URL-encoded

---

## Recommended .env Configuration for Azure SQL

```bash
# Azure SQL Connection String Format
DATABASE_URL=mssql+pyodbc://username:url_encoded_password@servername.database.windows.net/databasename?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30

# Example with values (replace with your actual values)
DATABASE_URL=mssql+pyodbc://admin_user:MyP%40ssw0rd@devsqlserver001.database.windows.net/fin-market-db?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no&Connection+Timeout=30
```

### Connection String Parameters Explained

| Parameter | Description | Recommended Value |
|-----------|-------------|-------------------|
| `driver` | ODBC driver name | `ODBC+Driver+18+for+SQL+Server` |
| `Encrypt` | Enable SSL/TLS | `yes` |
| `TrustServerCertificate` | Skip cert validation (dev only) | `no` (production), `yes` (dev) |
| `Connection+Timeout` | Connection timeout in seconds | `30-60` |
| `Timeout` | Query timeout in seconds | `30-60` |

---

## Dynamic IP Solutions

If your IP changes frequently:

### Option 1: Allow Azure Services
In Azure Portal → SQL Server → Networking:
- Enable **"Allow Azure services and resources to access this server"**
- Note: This is less secure, use only for development

### Option 2: Use Azure VPN or Private Endpoint
- Set up Azure VPN Gateway or Private Endpoint for secure access
- No firewall rules needed for private connections

### Option 3: Automation Script
Create a script to update firewall rules automatically:

```powershell
# update_azure_firewall.ps1
$myIP = (Invoke-WebRequest -Uri "https://api.ipify.org").Content
az sql server firewall-rule update `
  --resource-group YourResourceGroup `
  --server devsqlserver001 `
  --name MyDevMachine `
  --start-ip-address $myIP `
  --end-ip-address $myIP

Write-Host "Firewall rule updated for IP: $myIP"
```

Run before testing:
```powershell
.\update_azure_firewall.ps1
python tests/ingestion/test_candle_ingestion.py
```

---

## Troubleshooting Workflow

```
Connection Issue
    ↓
1. Check Azure SQL firewall rules
    ├─ Add your IP if missing
    └─ Wait 2-5 minutes
    ↓
2. Test basic connectivity
    └─ Test-NetConnection or ping server
    ↓
3. Verify .env configuration
    ├─ Check connection string format
    ├─ URL-encode special characters
    └─ Check credentials
    ↓
4. Test with simple query
    └─ python test_db_connection.py
    ↓
5. Run ingestion tests
    └─ python tests/ingestion/test_candle_ingestion.py
```

---

## Getting Help

If issues persist:

1. **Check Azure SQL Server Status**
   - Go to Azure Portal
   - Check if server is online and not paused

2. **Review Azure SQL Activity Log**
   - Azure Portal → SQL Server → Activity Log
   - Look for failed connection attempts

3. **Enable Diagnostic Logging**
   - Azure Portal → SQL Server → Diagnostic settings
   - Enable connection logs

4. **Test from Azure Cloud Shell**
   - Open Azure Cloud Shell in portal
   - Test connection from within Azure network
   - If this works, issue is firewall-related

5. **Contact Azure Support**
   - If all else fails, open Azure support ticket

---

## Summary

Most connection issues are caused by:
1. ❌ **Firewall rules** (90% of cases)
2. ❌ **Incorrect connection string**
3. ❌ **Network/VPN issues**

**Quick Fix for Most Issues**:
```powershell
# 1. Whitelist your IP in Azure Portal
# 2. Wait 2-5 minutes
# 3. Test connection
python -c "from cryptoquant.database.session import get_engine; get_engine().connect(); print('✅ Connected!')"
```

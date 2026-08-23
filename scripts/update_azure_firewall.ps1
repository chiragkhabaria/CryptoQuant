<parameter name="content"># Azure SQL Firewall Rule Updater
# Automatically adds your current IP to Azure SQL Server firewall rules

param(
    [Parameter(Mandatory=$false)]
    [string]$ResourceGroup = "",
    
    [Parameter(Mandatory=$false)]
    [string]$ServerName = "fin-market-sqlserver",
    
    [Parameter(Mandatory=$false)]
    [string]$RuleName = "LocalDevelopmentMachine",
    
    [Parameter(Mandatory=$false)]
    [switch]$Help
)

# Show help
if ($Help) {
    Write-Host @"
Azure SQL Firewall Rule Updater
================================

This script automatically adds your current public IP to Azure SQL Server firewall rules.

Usage:
    .\scripts\update_azure_firewall.ps1 -ResourceGroup "YourResourceGroup" -ServerName "fin-market-sqlserver"

Parameters:
    -ResourceGroup   : Azure resource group name (required)
    -ServerName      : SQL Server name (default: fin-market-sqlserver)
    -RuleName        : Firewall rule name (default: LocalDevelopmentMachine)
    -Help            : Show this help message

Prerequisites:
    - Azure CLI installed (az command)
    - Logged in to Azure (az login)
    - Permissions to modify SQL Server firewall rules

Examples:
    # Add current IP to firewall
    .\scripts\update_azure_firewall.ps1 -ResourceGroup "crypto-dev-rg"
    
    # Custom rule name
    .\scripts\update_azure_firewall.ps1 -ResourceGroup "crypto-dev-rg" -RuleName "MyWorkstation"

After running:
    Wait 2-5 minutes for changes to take effect, then test connection:
    python tests/ingestion/test_db_connection.py
"@
    exit 0
}

Write-Host ""
Write-Host "================================================================================"
Write-Host "  Azure SQL Firewall Rule Updater"
Write-Host "================================================================================"
Write-Host ""

# Check if ResourceGroup is provided
if ([string]::IsNullOrWhiteSpace($ResourceGroup)) {
    Write-Host "❌ ERROR: Resource Group name is required" -ForegroundColor Red
    Write-Host ""
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\scripts\update_azure_firewall.ps1 -ResourceGroup 'YourResourceGroup'" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "For help:" -ForegroundColor Yellow
    Write-Host "  .\scripts\update_azure_firewall.ps1 -Help" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

# Check if Azure CLI is installed
Write-Host "✓ Checking Azure CLI installation..." -ForegroundColor Cyan
try {
    $azVersion = az version --output json 2>$null | ConvertFrom-Json
    if ($azVersion) {
        Write-Host "  Azure CLI version: $($azVersion.'azure-cli')" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ ERROR: Azure CLI is not installed or not in PATH" -ForegroundColor Red
    Write-Host ""
    Write-Host "Install Azure CLI:" -ForegroundColor Yellow
    Write-Host "  https://docs.microsoft.com/en-us/cli/azure/install-azure-cli" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

# Check if logged in to Azure
Write-Host "✓ Checking Azure login status..." -ForegroundColor Cyan
try {
    $account = az account show --output json 2>$null | ConvertFrom-Json
    if ($account) {
        Write-Host "  Logged in as: $($account.user.name)" -ForegroundColor Green
        Write-Host "  Subscription: $($account.name)" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ ERROR: Not logged in to Azure" -ForegroundColor Red
    Write-Host ""
    Write-Host "Login to Azure:" -ForegroundColor Yellow
    Write-Host "  az login" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

# Get current public IP
Write-Host ""
Write-Host "✓ Getting your current public IP address..." -ForegroundColor Cyan
try {
    $myIP = (Invoke-WebRequest -Uri "https://api.ipify.org" -UseBasicParsing -TimeoutSec 10).Content
    Write-Host "  Your IP: $myIP" -ForegroundColor Green
} catch {
    Write-Host "❌ ERROR: Could not retrieve public IP address" -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Try manually:" -ForegroundColor Yellow
    Write-Host "  `$myIP = (Invoke-WebRequest -Uri 'https://api.ipify.org').Content" -ForegroundColor Yellow
    Write-Host "  Write-Host `$myIP" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}

# Check if firewall rule already exists
Write-Host ""
Write-Host "✓ Checking existing firewall rules..." -ForegroundColor Cyan
try {
    $existingRule = az sql server firewall-rule show `
        --resource-group $ResourceGroup `
        --server $ServerName `
        --name $RuleName `
        --output json 2>$null | ConvertFrom-Json
    
    if ($existingRule) {
        Write-Host "  Rule '$RuleName' exists with IP range: $($existingRule.startIpAddress) - $($existingRule.endIpAddress)" -ForegroundColor Yellow
        
        if ($existingRule.startIpAddress -eq $myIP -and $existingRule.endIpAddress -eq $myIP) {
            Write-Host ""
            Write-Host "✅ SUCCESS: Firewall rule already up to date!" -ForegroundColor Green
            Write-Host ""
            Write-Host "Your IP ($myIP) is already whitelisted." -ForegroundColor Green
            Write-Host ""
            Write-Host "Test your connection:" -ForegroundColor Cyan
            Write-Host "  python tests/ingestion/test_db_connection.py" -ForegroundColor Cyan
            Write-Host ""
            exit 0
        }
        
        Write-Host "  Updating rule to new IP address..." -ForegroundColor Yellow
    } else {
        Write-Host "  No existing rule found, creating new one..." -ForegroundColor Yellow
    }
} catch {
    # Rule doesn't exist, will create it
    Write-Host "  No existing rule found, creating new one..." -ForegroundColor Yellow
}

# Create or update firewall rule
Write-Host ""
Write-Host "✓ Creating/updating firewall rule..." -ForegroundColor Cyan
Write-Host "  Resource Group: $ResourceGroup" -ForegroundColor Gray
Write-Host "  Server: $ServerName" -ForegroundColor Gray
Write-Host "  Rule Name: $RuleName" -ForegroundColor Gray
Write-Host "  IP Address: $myIP" -ForegroundColor Gray
Write-Host ""

try {
    $rule = az sql server firewall-rule create `
        --resource-group $ResourceGroup `
        --server $ServerName `
        --name $RuleName `
        --start-ip-address $myIP `
        --end-ip-address $myIP `
        --output json 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ SUCCESS: Firewall rule created/updated successfully!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Firewall Rule Details:" -ForegroundColor Cyan
        Write-Host "  Name: $RuleName" -ForegroundColor Gray
        Write-Host "  IP Address: $myIP" -ForegroundColor Gray
        Write-Host "  Server: $ServerName.database.windows.net" -ForegroundColor Gray
        Write-Host ""
        Write-Host "⏱  IMPORTANT: Wait 2-5 minutes for changes to take effect" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Then test your connection:" -ForegroundColor Cyan
        Write-Host "  python tests/ingestion/test_db_connection.py" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "If successful, run the ingestion tests:" -ForegroundColor Cyan
        Write-Host "  python tests/ingestion/test_candle_ingestion.py" -ForegroundColor Cyan
        Write-Host ""
        exit 0
    } else {
        Write-Host "❌ ERROR: Failed to create/update firewall rule" -ForegroundColor Red
        Write-Host $rule -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ ERROR: Failed to create/update firewall rule" -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Common issues:" -ForegroundColor Yellow
    Write-Host "  1. Incorrect resource group name" -ForegroundColor Yellow
    Write-Host "  2. Insufficient permissions" -ForegroundColor Yellow
    Write-Host "  3. Server name is incorrect" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Verify your settings:" -ForegroundColor Cyan
    Write-Host "  az sql server list --resource-group $ResourceGroup --output table" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

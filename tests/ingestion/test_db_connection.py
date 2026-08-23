#!/usr/bin/env python
"""
Database Connection Test Utility

Tests database connectivity and provides troubleshooting information.
Run this before executing ingestion tests to verify database access.

Usage:
    python tests/ingestion/test_db_connection.py
"""

import sys
from pathlib import Path
from datetime import datetime
import traceback

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from sqlalchemy import text
from cryptoquant.database.session import get_engine
from cryptoquant.config.settings import get_settings


def print_section(title: str):
    """Print formatted section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_database_connection():
    """Test database connection and print diagnostic information."""
    print_section("DATABASE CONNECTION TEST")
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Load settings
        print("\n✓ Loading configuration...")
        settings = get_settings()
        
        # Mask sensitive data in connection string
        db_url = settings.database_url
        if '@' in db_url:
            parts = db_url.split('@')
            credentials = parts[0].split('://')[-1]
            username = credentials.split(':')[0]
            rest = '@'.join(parts[1:])
            masked_url = f"...://{username}:***@{rest}"
        else:
            masked_url = db_url
        
        print(f"✓ Database URL: {masked_url}")
        print(f"✓ Environment: {settings.environment}")
        
    except Exception as e:
        print(f"\n❌ FAILED: Could not load configuration")
        print(f"Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Ensure .env file exists in project root")
        print("  2. Verify DATABASE_URL is set in .env file")
        print("  3. Check for syntax errors in .env file")
        return False
    
    try:
        # Create engine
        print("\n✓ Creating database engine...")
        engine = get_engine()
        print(f"✓ Engine created successfully")
        print(f"✓ Database: {engine.url.database}")
        print(f"✓ Driver: {engine.driver}")
        
    except Exception as e:
        print(f"\n❌ FAILED: Could not create database engine")
        print(f"Error: {e}")
        print("\nTroubleshooting:")
        print("  1. Verify ODBC Driver 18 for SQL Server is installed")
        print("  2. Check connection string format in .env file")
        print("  3. Ensure special characters in password are URL-encoded")
        return False
    
    try:
        # Test connection
        print("\n✓ Testing database connection...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 AS test"))
            row = result.fetchone()
            if row and row[0] == 1:
                print("✓ Connection successful!")
            else:
                print("⚠ Warning: Unexpected result from test query")
                
    except Exception as e:
        error_msg = str(e)
        print(f"\n❌ FAILED: Could not connect to database")
        print(f"Error: {error_msg}")
        
        # Provide specific troubleshooting based on error
        print("\n" + "=" * 80)
        print("  TROUBLESHOOTING")
        print("=" * 80)
        
        if "40615" in error_msg or "not allowed to access" in error_msg:
            print("\n🔥 FIREWALL ISSUE DETECTED")
            print("\nYour IP address is not whitelisted in Azure SQL Server firewall.")
            print("\nSOLUTION:")
            print("  1. Go to Azure Portal: https://portal.azure.com")
            print("  2. Navigate to your SQL Server")
            print("  3. Click 'Networking' or 'Firewalls and virtual networks'")
            print("  4. Click '+ Add client IP' to whitelist your current IP")
            print("  5. Click 'Save' and wait 2-5 minutes")
            print("\nAlternatively, use Azure CLI:")
            print("  $myIP = (Invoke-WebRequest -Uri 'https://api.ipify.org').Content")
            print("  az sql server firewall-rule create --resource-group YourResourceGroup \\")
            print("    --server devsqlserver001 --name MyDevMachine \\")
            print("    --start-ip-address $myIP --end-ip-address $myIP")
            
        elif "timeout" in error_msg.lower() or "258" in error_msg:
            print("\n⏱ CONNECTION TIMEOUT DETECTED")
            print("\nPossible causes:")
            print("  1. Firewall is blocking the connection")
            print("  2. Network latency or VPN issues")
            print("  3. Azure SQL server is busy or unavailable")
            print("\nSOLUTIONS:")
            print("  1. Check firewall rules (see above)")
            print("  2. Increase timeout in DATABASE_URL:")
            print("     Add '&Connection+Timeout=60' to your connection string")
            print("  3. Test network connectivity:")
            print("     Test-NetConnection -ComputerName devsqlserver001.database.windows.net -Port 1433")
            print("  4. Temporarily disable VPN and retry")
            
        elif "login failed" in error_msg.lower():
            print("\n🔐 AUTHENTICATION FAILED")
            print("\nPossible causes:")
            print("  1. Incorrect username or password")
            print("  2. Special characters in password not URL-encoded")
            print("  3. User doesn't have access to the database")
            print("\nSOLUTIONS:")
            print("  1. Verify credentials in .env file")
            print("  2. URL-encode special characters in password:")
            print("     @ → %40, # → %23, & → %26, etc.")
            print("  3. Test credentials with sqlcmd:")
            print("     sqlcmd -S server.database.windows.net -d database -U user -P password")
            
        elif "certificate" in error_msg.lower() or "ssl" in error_msg.lower():
            print("\n🔒 SSL/TLS CERTIFICATE ISSUE")
            print("\nSOLUTION:")
            print("  Add 'TrustServerCertificate=yes' to your DATABASE_URL:")
            print("  DATABASE_URL=...?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes")
            
        else:
            print("\n❓ UNIDENTIFIED ERROR")
            print("\nGeneral troubleshooting steps:")
            print("  1. Check .env file for correct DATABASE_URL format")
            print("  2. Verify ODBC Driver 18 for SQL Server is installed")
            print("  3. Test basic network connectivity")
            print("  4. Check Azure SQL server status in Azure Portal")
            print("  5. Review logs for detailed error information")
        
        print("\n" + "=" * 80)
        print("  DOCUMENTATION")
        print("=" * 80)
        print("\nFor detailed troubleshooting, see:")
        print("  docs/testing/AZURE_SQL_TROUBLESHOOTING.md")
        print("\n" + "=" * 80)
        
        return False
    
    try:
        # Test query execution
        print("\n✓ Testing query execution...")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    SERVERPROPERTY('ProductVersion') AS version,
                    SERVERPROPERTY('Edition') AS edition,
                    DB_NAME() AS current_database
            """))
            row = result.fetchone()
            if row:
                print(f"✓ SQL Server Version: {row[0]}")
                print(f"✓ Edition: {row[1]}")
                print(f"✓ Current Database: {row[2]}")
                
    except Exception as e:
        print(f"\n⚠ Warning: Could not retrieve server information")
        print(f"Error: {e}")
        # This is not critical, so we continue
    
    try:
        # Test schema access
        print("\n✓ Testing schema access...")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    SCHEMA_NAME(schema_id) AS schema_name,
                    name AS table_name
                FROM sys.tables
                WHERE SCHEMA_NAME(schema_id) = 'crypto'
                ORDER BY name
            """))
            tables = result.fetchall()
            
            if tables:
                print(f"✓ Found {len(tables)} tables in 'crypto' schema:")
                for table in tables[:10]:  # Show first 10 tables
                    print(f"    - crypto.{table[1]}")
                if len(tables) > 10:
                    print(f"    ... and {len(tables) - 10} more")
            else:
                print("⚠ Warning: No tables found in 'crypto' schema")
                print("  You may need to run database migrations:")
                print("    python scripts/db_migrate.py")
                
    except Exception as e:
        print(f"\n⚠ Warning: Could not access schema information")
        print(f"Error: {e}")
        # This is not critical if the connection works
    
    # Success!
    print("\n" + "=" * 80)
    print("  ✅ DATABASE CONNECTION TEST PASSED")
    print("=" * 80)
    print("\nYour database connection is working correctly!")
    print("You can now run the ingestion tests:")
    print("  python tests/ingestion/test_candle_ingestion.py")
    print("\n" + "=" * 80)
    
    return True


def main():
    """Main entry point."""
    success = test_database_connection()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

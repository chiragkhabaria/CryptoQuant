"""
Database Reset Script

Drop and recreate all database tables.

WARNING: This will delete all data. Use only in development.

Usage:
    python scripts/db_reset.py [--url DATABASE_URL] [--confirm]
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from cryptoquant.config.settings import get_settings
from cryptoquant.database.session import drop_database, init_database


def main() -> None:
    """Reset database (drop and recreate tables)."""
    parser = argparse.ArgumentParser(description="Reset database (DEVELOPMENT ONLY)")
    parser.add_argument(
        "--url",
        help="Database URL (overrides .env)",
        default=None,
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Skip confirmation prompt",
    )
    args = parser.parse_args()

    if args.url:
        import os
        os.environ["DATABASE_URL"] = args.url

    # Safety check
    settings = get_settings()
    if settings.is_production:
        print("✗ Cannot reset database in production environment")
        sys.exit(1)

    # Confirm with user
    if not args.confirm:
        response = input("⚠️  This will delete ALL data. Continue? (yes/no): ")
        if response.lower() != "yes":
            print("Cancelled")
            sys.exit(0)

    try:
        print("Dropping all tables...")
        drop_database()
        print("✓ All tables dropped")

        print("\nRecreating schema...")
        init_database()
        print("✓ Database reset successfully")
    except Exception as e:
        print(f"✗ Reset failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

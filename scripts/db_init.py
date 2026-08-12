"""
Database Initialization Script

Initialize database schema from scratch.

Usage:
    python scripts/db_init.py [--url DATABASE_URL]
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from cryptoquant.database.session import init_database


def main() -> None:
    """Initialize database schema."""
    parser = argparse.ArgumentParser(description="Initialize database schema")
    parser.add_argument(
        "--url",
        help="Database URL (overrides .env)",
        default=None,
    )
    args = parser.parse_args()

    if args.url:
        import os
        os.environ["DATABASE_URL"] = args.url

    try:
        print("Initializing database schema...")
        init_database()
        print("✓ Database schema initialized successfully")
        print("\nCreated tables:")
        print("  - assets")
        print("  - trading_pairs")
        print("  - market_prices")
    except Exception as e:
        print(f"✗ Initialization failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

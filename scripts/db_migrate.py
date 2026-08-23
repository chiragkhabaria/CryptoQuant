"""
Database Migration Script

Apply database migrations using Alembic.

Usage:
    python scripts/db_migrate.py [--url DATABASE_URL]
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from alembic import command
from alembic.config import Config


def main() -> None:
    """Run database migrations."""
    parser = argparse.ArgumentParser(description="Apply database migrations")
    parser.add_argument(
        "--url",
        help="Database URL (overrides .env)",
        default=None,
    )
    parser.add_argument(
        "--revision",
        help="Target revision (defaults to 'head')",
        default="head",
    )
    args = parser.parse_args()

    # Configure Alembic
    alembic_cfg = Config(str(project_root / "alembic.ini"))
    
    if args.url:
        alembic_cfg.set_main_option("sqlalchemy.url", args.url)

    try:
        print(f"Applying migrations to revision: {args.revision}")
        command.upgrade(alembic_cfg, args.revision)
        print("✓ Migrations applied successfully")
    except Exception as e:
        print(f"✗ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

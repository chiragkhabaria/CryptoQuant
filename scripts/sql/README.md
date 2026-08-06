# SQL Scripts

This directory contains SQL migration scripts and database utilities.

## Structure

- `migrations/` - Alembic migration files
- `schema/` - Initial schema definitions
- `queries/` - Common analytical queries
- `maintenance/` - Database maintenance scripts

## Usage

Migrations are managed by Alembic:

```bash
# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

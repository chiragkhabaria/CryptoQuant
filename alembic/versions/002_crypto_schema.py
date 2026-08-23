"""Add crypto schema and enhanced trading pair columns

Revision ID: 002
Revises: 001
Create Date: 2026-08-07 12:00:00.000000

This migration:
1. Creates the 'crypto' schema
2. Recreates tables under crypto schema with enhanced columns
3. Migrates any existing data (if applicable)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create crypto schema and enhanced tables."""
    
    # Step 1: Create crypto schema
    op.execute("CREATE SCHEMA crypto")
    
    # Step 2: Create assets table in crypto schema
    op.create_table('assets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('display_symbol', sa.String(length=20), nullable=True),
        sa.Column('asset_type', sa.String(length=20), nullable=False),
        sa.Column('decimals', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='crypto'
    )
    op.create_index('ix_crypto_assets_symbol', 'assets', ['symbol'], unique=True, schema='crypto')
    op.create_index('ix_crypto_assets_active', 'assets', ['active'], unique=False, schema='crypto')

    # Step 3: Create trading_pairs table in crypto schema with enhanced columns
    op.create_table('trading_pairs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('base_asset_id', sa.Integer(), nullable=False),
        sa.Column('quote_asset_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('trading_disabled', sa.Boolean(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('base_increment', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('quote_increment', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('base_min_size', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('base_max_size', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('quote_min_size', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('quote_max_size', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()'), nullable=False),
        sa.ForeignKeyConstraint(['base_asset_id'], ['crypto.assets.id'], ),
        sa.ForeignKeyConstraint(['quote_asset_id'], ['crypto.assets.id'], ),
        sa.PrimaryKeyConstraint('id'),
        schema='crypto'
    )
    op.create_index('ix_crypto_trading_pairs_symbol', 'trading_pairs', ['symbol'], unique=True, schema='crypto')
    op.create_index('ix_crypto_trading_pairs_active', 'trading_pairs', ['active'], unique=False, schema='crypto')

    # Step 4: Create market_prices table in crypto schema
    op.create_table('market_prices',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('trading_pair_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('open', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('high', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('low', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('close', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('volume', sa.Numeric(precision=18, scale=8), nullable=False),
        sa.Column('data_source', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()'), nullable=False),
        sa.ForeignKeyConstraint(['trading_pair_id'], ['crypto.trading_pairs.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('trading_pair_id', 'timestamp', name='uq_market_price_pair_timestamp'),
        schema='crypto'
    )
    op.create_index('ix_crypto_market_prices_pair_time', 'market_prices', ['trading_pair_id', 'timestamp'], unique=False, schema='crypto')
    op.create_index('ix_crypto_market_prices_timestamp_desc', 'market_prices', ['timestamp'], unique=False, schema='crypto')
    op.create_index('ix_crypto_market_prices_trading_pair_id', 'market_prices', ['trading_pair_id'], unique=False, schema='crypto')

    # Step 5: Drop old tables from dbo schema (if they exist)
    # Note: Only run this if you're sure you don't need the old data
    # You can comment these out if you want to manually migrate data first
    try:
        op.drop_index('ix_market_prices_trading_pair_id', table_name='market_prices')
        op.drop_index('ix_market_prices_timestamp_desc', table_name='market_prices')
        op.drop_index('ix_market_prices_pair_time', table_name='market_prices')
        op.drop_table('market_prices')
    except:
        pass  # Table may not exist
    
    try:
        op.drop_index('ix_trading_pairs_active', table_name='trading_pairs')
        op.drop_index('ix_trading_pairs_symbol', table_name='trading_pairs')
        op.drop_table('trading_pairs')
    except:
        pass  # Table may not exist
    
    try:
        op.drop_index('ix_assets_active', table_name='assets')
        op.drop_index('ix_assets_symbol', table_name='assets')
        op.drop_table('assets')
    except:
        pass  # Table may not exist


def downgrade() -> None:
    """Remove crypto schema and tables."""
    
    # Drop crypto schema tables
    op.drop_index('ix_crypto_market_prices_trading_pair_id', table_name='market_prices', schema='crypto')
    op.drop_index('ix_crypto_market_prices_timestamp_desc', table_name='market_prices', schema='crypto')
    op.drop_index('ix_crypto_market_prices_pair_time', table_name='market_prices', schema='crypto')
    op.drop_table('market_prices', schema='crypto')
    
    op.drop_index('ix_crypto_trading_pairs_active', table_name='trading_pairs', schema='crypto')
    op.drop_index('ix_crypto_trading_pairs_symbol', table_name='trading_pairs', schema='crypto')
    op.drop_table('trading_pairs', schema='crypto')
    
    op.drop_index('ix_crypto_assets_active', table_name='assets', schema='crypto')
    op.drop_index('ix_crypto_assets_symbol', table_name='assets', schema='crypto')
    op.drop_table('assets', schema='crypto')
    
    # Drop crypto schema
    op.execute("DROP SCHEMA crypto")

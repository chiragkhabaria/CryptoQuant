"""Initial schema - Assets, TradingPairs, MarketPrices

Revision ID: 001
Revises: 
Create Date: 2026-08-05 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create assets table
    op.create_table('assets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('asset_type', sa.String(length=20), nullable=False),
        sa.Column('decimals', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_assets_symbol', 'assets', ['symbol'], unique=True)
    op.create_index('ix_assets_active', 'assets', ['active'], unique=False)

    # Create trading_pairs table
    op.create_table('trading_pairs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('base_asset_id', sa.Integer(), nullable=False),
        sa.Column('quote_asset_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('min_order_size', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('max_order_size', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('GETUTCDATE()'), nullable=False),
        sa.ForeignKeyConstraint(['base_asset_id'], ['assets.id'], ),
        sa.ForeignKeyConstraint(['quote_asset_id'], ['assets.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_trading_pairs_symbol', 'trading_pairs', ['symbol'], unique=True)
    op.create_index('ix_trading_pairs_active', 'trading_pairs', ['active'], unique=False)

    # Create market_prices table
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
        sa.ForeignKeyConstraint(['trading_pair_id'], ['trading_pairs.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('trading_pair_id', 'timestamp', name='uq_market_price_pair_timestamp')
    )
    op.create_index('ix_market_prices_pair_time', 'market_prices', ['trading_pair_id', 'timestamp'], unique=False)
    op.create_index('ix_market_prices_timestamp_desc', 'market_prices', ['timestamp'], unique=False)
    op.create_index('ix_market_prices_trading_pair_id', 'market_prices', ['trading_pair_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_market_prices_trading_pair_id', table_name='market_prices')
    op.drop_index('ix_market_prices_timestamp_desc', table_name='market_prices')
    op.drop_index('ix_market_prices_pair_time', table_name='market_prices')
    op.drop_table('market_prices')
    op.drop_index('ix_trading_pairs_active', table_name='trading_pairs')
    op.drop_index('ix_trading_pairs_symbol', table_name='trading_pairs')
    op.drop_table('trading_pairs')
    op.drop_index('ix_assets_active', table_name='assets')
    op.drop_index('ix_assets_symbol', table_name='assets')
    op.drop_table('assets')

"""Add technical_analysis table for Phase 2 indicators

Revision ID: 006
Revises: 005
Create Date: 2026-08-24 12:00:00.000000

This migration creates the crypto.technical_analysis table to store
calculated technical indicators (EMA, RSI, MACD, ATR), scores, and signals.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006'
down_revision: Union[str, None] = '005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create technical_analysis table."""
    
    op.create_table(
        'technical_analysis',
        # Primary Key
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        
        # Relationships
        sa.Column('market_price_id', sa.Integer(), nullable=False),
        sa.Column('trading_pair_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        
        # Technical Indicators
        sa.Column('ema_200', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('rsi_14', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('macd', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('macd_signal', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('macd_histogram', sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column('atr_14', sa.Numeric(precision=18, scale=8), nullable=True),
        
        # Scoring (placeholders for Phase 3)
        sa.Column('ema_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('rsi_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('macd_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('atr_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('technical_score', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('signal', sa.String(length=10), nullable=True),
        
        # Metadata
        sa.Column('calculation_version', sa.String(length=10), nullable=False, server_default='v1'),
        sa.Column('calculated_at', sa.DateTime(), nullable=False, server_default=sa.text('GETUTCDATE()')),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['market_price_id'], ['crypto.market_prices.id']),
        sa.ForeignKeyConstraint(['trading_pair_id'], ['crypto.trading_pairs.id']),
        sa.UniqueConstraint('market_price_id', name='uq_technical_analysis_market_price'),
        sa.UniqueConstraint('trading_pair_id', 'timestamp', name='uq_technical_analysis_pair_timestamp'),
        
        schema='crypto'
    )
    
    # Create indexes
    op.create_index(
        'ix_technical_analysis_timestamp',
        'technical_analysis',
        ['timestamp'],
        unique=False,
        schema='crypto'
    )
    
    op.create_index(
        'ix_technical_analysis_signal',
        'technical_analysis',
        ['signal'],
        unique=False,
        schema='crypto',
        postgresql_where=sa.text("signal IS NOT NULL")
    )
    
    op.create_index(
        'ix_technical_analysis_version',
        'technical_analysis',
        ['calculation_version'],
        unique=False,
        schema='crypto'
    )


def downgrade() -> None:
    """Drop technical_analysis table."""
    
    op.drop_index('ix_technical_analysis_version', table_name='technical_analysis', schema='crypto')
    op.drop_index('ix_technical_analysis_signal', table_name='technical_analysis', schema='crypto')
    op.drop_index('ix_technical_analysis_timestamp', table_name='technical_analysis', schema='crypto')
    op.drop_table('technical_analysis', schema='crypto')

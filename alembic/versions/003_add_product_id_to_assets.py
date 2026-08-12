"""Add product_id to assets table

Revision ID: 003
Revises: 002
Create Date: 2026-08-07 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add product_id column to crypto.assets table"""
    # Add product_id column after id
    op.add_column(
        'assets',
        sa.Column('product_id', sa.String(50), nullable=True, comment='Sample product ID where this asset appears'),
        schema='crypto'
    )
    
    # Create index on product_id
    op.create_index(
        'ix_crypto_assets_product_id',
        'assets',
        ['product_id'],
        schema='crypto'
    )


def downgrade() -> None:
    """Remove product_id column from crypto.assets table"""
    op.drop_index('ix_crypto_assets_product_id', table_name='assets', schema='crypto')
    op.drop_column('assets', 'product_id', schema='crypto')

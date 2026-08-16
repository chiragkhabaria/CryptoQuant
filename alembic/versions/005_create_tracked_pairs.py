"""Create tracked pairs table

Revision ID: 005
Revises: 003
Create Date: 2026-08-11 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from pathlib import Path


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create tracked_pairs table and insert initial seed data"""
    
    # Create tracked_pairs table
    op.create_table(
        'tracked_pairs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('product_id', sa.String(length=50), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('is_tracking_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('modified_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', name='uq_tracked_pairs_product_id'),
        schema='crypto'
    )
    
    # Create indexes
    op.create_index('ix_crypto_tracked_pairs_product_id', 'tracked_pairs', ['product_id'], unique=True, schema='crypto')
    op.create_index('ix_crypto_tracked_pairs_symbol', 'tracked_pairs', ['symbol'], schema='crypto')
    op.create_index('ix_crypto_tracked_pairs_is_tracking_active', 'tracked_pairs', ['is_tracking_active'], schema='crypto')
    
    # Execute seed data from SQL file
    seed_sql_path = Path(__file__).parent.parent.parent / 'scripts' / 'sql' / 'seed_tracked_pairs.sql'
    if seed_sql_path.exists():
        seed_sql = seed_sql_path.read_text()
        # Extract and execute INSERT statement
        lines = []
        in_insert = False
        for line in seed_sql.split('\n'):
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('--'):
                continue
            # Start of INSERT statement
            if line.startswith('INSERT INTO'):
                in_insert = True
                lines = [line]
            elif in_insert:
                lines.append(line)
                # End of INSERT when we hit semicolon
                if line.endswith(';'):
                    insert_stmt = ' '.join(lines)
                    op.execute(insert_stmt)
                    in_insert = False
                    lines = []


def downgrade() -> None:
    """Drop tracked_pairs table"""
    op.drop_index('ix_crypto_tracked_pairs_is_tracking_active', table_name='tracked_pairs', schema='crypto')
    op.drop_index('ix_crypto_tracked_pairs_symbol', table_name='tracked_pairs', schema='crypto')
    op.drop_index('ix_crypto_tracked_pairs_product_id', table_name='tracked_pairs', schema='crypto')
    op.drop_table('tracked_pairs', schema='crypto')

"""Add job_runs table

Revision ID: 008
Revises: 007
Create Date: 2026-10-31 19:30:00.000000

Creates crypto.job_runs: a log of scheduled and UI-triggered job executions.
UI-triggered jobs are inserted as 'queued' and picked up by a worker.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'job_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('job_type', sa.String(length=30), nullable=False),
        sa.Column('status', sa.String(length=10), nullable=False),
        sa.Column('triggered_by', sa.String(length=20), nullable=False, server_default='scheduler'),
        sa.Column('params', sa.Text(), nullable=True),
        sa.Column('rows_written', sa.Integer(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('GETUTCDATE()')),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='crypto',
    )
    op.create_index('ix_job_runs_job_type', 'job_runs', ['job_type'], schema='crypto')
    op.create_index('ix_job_runs_status', 'job_runs', ['status'], schema='crypto')
    op.create_index('ix_job_runs_created_at', 'job_runs', ['created_at'], schema='crypto')


def downgrade() -> None:
    op.drop_index('ix_job_runs_created_at', table_name='job_runs', schema='crypto')
    op.drop_index('ix_job_runs_status', table_name='job_runs', schema='crypto')
    op.drop_index('ix_job_runs_job_type', table_name='job_runs', schema='crypto')
    op.drop_table('job_runs', schema='crypto')

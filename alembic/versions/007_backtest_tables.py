"""Add backtest tables and summary view

Revision ID: 007
Revises: 006
Create Date: 2026-10-31 18:00:00.000000

Creates crypto.backtest_runs, crypto.backtest_trades, crypto.backtest_equity
and the crypto.vw_backtest_summary view.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '007'
down_revision: Union[str, None] = '006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'backtest_runs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('trading_pair_id', sa.Integer(), nullable=False),
        sa.Column('strategy_name', sa.String(length=50), nullable=False),
        sa.Column('strategy_params', sa.Text(), nullable=False),
        sa.Column('scoring_version', sa.String(length=10), nullable=False, server_default='v1'),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('initial_capital', sa.Numeric(18, 2), nullable=False),
        sa.Column('fee_bps', sa.Numeric(8, 2), nullable=False),
        sa.Column('slippage_bps', sa.Numeric(8, 2), nullable=False),
        sa.Column('stop_atr_mult', sa.Numeric(6, 2), nullable=True),
        sa.Column('total_return', sa.Numeric(12, 6), nullable=True),
        sa.Column('benchmark_return', sa.Numeric(12, 6), nullable=True),
        sa.Column('excess_return', sa.Numeric(12, 6), nullable=True),
        sa.Column('cagr', sa.Numeric(12, 6), nullable=True),
        sa.Column('max_drawdown', sa.Numeric(12, 6), nullable=True),
        sa.Column('sharpe', sa.Numeric(12, 6), nullable=True),
        sa.Column('win_rate', sa.Numeric(12, 6), nullable=True),
        sa.Column('profit_factor', sa.Numeric(12, 6), nullable=True),
        sa.Column('avg_trade_return', sa.Numeric(12, 6), nullable=True),
        sa.Column('exposure', sa.Numeric(12, 6), nullable=True),
        sa.Column('num_trades', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('num_bars', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_fees', sa.Numeric(18, 2), nullable=True),
        sa.Column('final_equity', sa.Numeric(18, 2), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('GETUTCDATE()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['trading_pair_id'], ['crypto.trading_pairs.id']),
        schema='crypto',
    )
    op.create_index('ix_backtest_runs_trading_pair_id', 'backtest_runs', ['trading_pair_id'], schema='crypto')
    op.create_index('ix_backtest_runs_strategy_name', 'backtest_runs', ['strategy_name'], schema='crypto')
    op.create_index('ix_backtest_runs_created_at', 'backtest_runs', ['created_at'], schema='crypto')

    op.create_table(
        'backtest_trades',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('entry_time', sa.DateTime(), nullable=False),
        sa.Column('exit_time', sa.DateTime(), nullable=False),
        sa.Column('entry_price', sa.Numeric(18, 8), nullable=False),
        sa.Column('exit_price', sa.Numeric(18, 8), nullable=False),
        sa.Column('quantity', sa.Numeric(28, 12), nullable=False),
        sa.Column('fees', sa.Numeric(18, 4), nullable=False),
        sa.Column('pnl', sa.Numeric(18, 4), nullable=False),
        sa.Column('return_pct', sa.Numeric(12, 6), nullable=False),
        sa.Column('bars_held', sa.Integer(), nullable=False),
        sa.Column('exit_reason', sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['run_id'], ['crypto.backtest_runs.id'], ondelete='CASCADE'),
        schema='crypto',
    )
    op.create_index('ix_backtest_trades_run_id', 'backtest_trades', ['run_id'], schema='crypto')

    op.create_table(
        'backtest_equity',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('equity', sa.Numeric(18, 4), nullable=False),
        sa.Column('drawdown', sa.Numeric(12, 6), nullable=False),
        sa.Column('benchmark_equity', sa.Numeric(18, 4), nullable=False),
        sa.Column('in_position', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['run_id'], ['crypto.backtest_runs.id'], ondelete='CASCADE'),
        schema='crypto',
    )
    op.create_index('ix_backtest_equity_run_id', 'backtest_equity', ['run_id'], schema='crypto')
    op.create_index('ix_backtest_equity_run_time', 'backtest_equity', ['run_id', 'timestamp'], schema='crypto')

    op.execute(
        """
        CREATE VIEW crypto.vw_backtest_summary AS
        SELECT r.id AS run_id, r.created_at, tp.symbol AS pair, r.strategy_name,
               r.start_time, r.end_time, r.num_trades, r.total_return,
               r.benchmark_return, r.excess_return, r.cagr, r.max_drawdown,
               r.sharpe, r.win_rate, r.profit_factor, r.exposure,
               r.total_fees, r.final_equity, r.strategy_params
        FROM crypto.backtest_runs r
        JOIN crypto.trading_pairs tp ON tp.id = r.trading_pair_id
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW crypto.vw_backtest_summary")
    op.drop_index('ix_backtest_equity_run_time', table_name='backtest_equity', schema='crypto')
    op.drop_index('ix_backtest_equity_run_id', table_name='backtest_equity', schema='crypto')
    op.drop_table('backtest_equity', schema='crypto')
    op.drop_index('ix_backtest_trades_run_id', table_name='backtest_trades', schema='crypto')
    op.drop_table('backtest_trades', schema='crypto')
    op.drop_index('ix_backtest_runs_created_at', table_name='backtest_runs', schema='crypto')
    op.drop_index('ix_backtest_runs_strategy_name', table_name='backtest_runs', schema='crypto')
    op.drop_index('ix_backtest_runs_trading_pair_id', table_name='backtest_runs', schema='crypto')
    op.drop_table('backtest_runs', schema='crypto')

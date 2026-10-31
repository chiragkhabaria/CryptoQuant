"""Backtest results and what the score means."""

import streamlit as st

from cryptoquant.database.job_runs import JOB_BACKTEST, JOB_RESCORE
from cryptoquantui import queries
from cryptoquantui.components import charts
from cryptoquantui.components.actions import job_button
from cryptoquantui.components.style import pct
from cryptoquantui.services import backtests as bt

st.title("Backtests & score")

with st.expander("How the score works", expanded=False):
    info = bt.score_explainer()
    st.write(info["summary"])
    st.dataframe(info["components"], hide_index=True, use_container_width=True)

runs = queries.latest_backtests()
agg = bt.aggregate_summary(runs)
c1, c2 = st.columns(2)
c1.metric("Pairs beating buy & hold", f"{agg['beating']}/{agg['runs']}")
c2.metric("Avg excess return", pct(agg["avg_excess"]))

if runs.empty:
    st.info("No backtest runs yet. Run backtests below.")
else:
    table = runs.assign(verdict=runs.apply(bt.verdict, axis=1))
    st.dataframe(
        table[["symbol", "verdict", "total_return", "benchmark_return", "excess_return", "max_drawdown",
               "sharpe", "win_rate", "num_trades"]],
        hide_index=True, use_container_width=True,
    )

    symbol = st.selectbox("Pair detail", runs["symbol"].tolist())
    row = runs[runs["symbol"] == symbol].iloc[0]
    run_id = int(row["run_id"])
    k1, k2 = st.columns(2)
    k1.metric("Return", pct(row["total_return"]), f"{pct(row['excess_return'])} vs hold")
    k2.metric("Max drawdown", pct(row["max_drawdown"]))
    st.caption(bt.verdict(row))

    curve = queries.equity_curve(run_id)
    if not curve.empty:
        st.plotly_chart(charts.equity_chart(curve), use_container_width=True)
        st.plotly_chart(charts.drawdown_chart(curve), use_container_width=True)
    with st.expander("Trades"):
        st.dataframe(queries.trades(run_id), hide_index=True, use_container_width=True)

    st.subheader("Does a high score precede gains?")
    horizon = st.select_slider("Forward horizon (hours)", [1, 4, 12, 24, 72, 168], value=24)
    buckets = queries.score_buckets(symbol, horizon)
    if buckets.empty:
        st.info("Not enough scored history.")
    else:
        st.plotly_chart(charts.bucket_chart(buckets), use_container_width=True)
        st.dataframe(buckets, hide_index=True, use_container_width=True)

st.subheader("Signal mix")
days = st.select_slider("Last N days", [1, 7, 30, 90], value=7)
dist = queries.signal_distribution(days)
if not dist.empty:
    st.plotly_chart(charts.signal_chart(dist), use_container_width=True)

st.subheader("Actions")
fee = st.number_input("Fee (bps)", 0.0, 200.0, 40.0, 5.0)
slip = st.number_input("Slippage (bps)", 0.0, 100.0, 5.0, 1.0)
use_stop = st.checkbox("ATR stop-loss")
stop = st.number_input("Stop (ATR multiple)", 0.5, 10.0, 3.0, 0.5) if use_stop else None
job_button(JOB_BACKTEST, {"fee_bps": fee, "slippage_bps": slip, "stop_atr_mult": stop})
job_button(JOB_RESCORE)

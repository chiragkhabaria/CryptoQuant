"""Per-coin overview and interactive charts."""

import streamlit as st

from cryptoquantui import queries
from cryptoquantui.components import charts
from cryptoquantui.components.style import pct
from cryptoquantui.components.tables import copyable_table
from cryptoquantui.services import coins

st.title("Coins")

window_label = st.radio("Window", list(coins.WINDOWS), horizontal=True)
overview = queries.overview(coins.WINDOWS[window_label])

if overview.empty:
    st.info("No tracked pairs found.")
    st.stop()

st.caption(f"change_pct = price change over the last {window_label}. Use 📋 to copy a row as JSON.")
copyable_table(overview)

st.subheader("Chart")
symbols = queries.symbols()
default = coins.default_symbol(symbols)
symbol = st.selectbox("Coin", symbols, index=symbols.index(default) if default in symbols else 0)

c1, c2 = st.columns(2)
interval = c1.selectbox("Interval", list(coins.RESAMPLE_RULES), index=0)
lookback = c2.selectbox("Lookback", [7, 14, 30, 90, 180], index=1, format_func=lambda d: f"{d} days")

t1, t2, t3, t4 = st.columns(4)
ema = t1.toggle("EMA200", True)
rsi = t2.toggle("RSI", True)
macd = t3.toggle("MACD", False)
score = t4.toggle("Score", True)

candles = queries.coin_candles(symbol, lookback)
if candles.empty:
    st.info("No candles for this pair in the selected range.")
else:
    candles = coins.resample_candles(candles, coins.RESAMPLE_RULES[interval])
    st.plotly_chart(charts.price_chart(candles, symbol, ema, rsi, macd, score), width="stretch")
    last = overview[overview["symbol"] == symbol]
    if not last.empty:
        r = last.iloc[0]
        m1, m2, m3 = st.columns(3)
        m1.metric("Score", "-" if r["score"] != r["score"] else f"{r['score']:.0f}", r["signal"])
        m2.metric("RSI", "-" if r["rsi"] != r["rsi"] else f"{r['rsi']:.0f}")
        m3.metric("Backtest vs hold", pct(r["backtest_vs_hold"]))

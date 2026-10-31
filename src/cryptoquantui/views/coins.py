"""Per-coin overview and interactive charts."""

import streamlit as st

from cryptoquantui import queries
from cryptoquantui.components import charts
from cryptoquantui.components.style import pct
from cryptoquantui.components.tables import copyable_table
from cryptoquantui.services import coins

MAX_DAYS = 3650
LOOKBACKS = {"1D": 1, "7D": 7, "14D": 14, "30D": 30, "90D": 90, "180D": 180, "1Y": 365, "Max": MAX_DAYS}
MAX_POINTS = 4000

st.title("Coins")

symbols = queries.symbols()
if not symbols:
    st.info("No tracked pairs found.")
    st.stop()
default = coins.default_symbol(symbols)

with st.expander("📈 Chart", expanded=True):
    c1, c2, c3 = st.columns([2, 1, 1])
    symbol = c1.selectbox("Coin", symbols, index=symbols.index(default) if default in symbols else 0)
    interval = c2.selectbox("Interval", list(coins.RESAMPLE_RULES), index=0)
    lookback_label = c3.selectbox("Lookback", list(LOOKBACKS), index=2)

    candles = queries.coin_candles(symbol, LOOKBACKS[lookback_label])
    if candles.empty:
        st.info("No candles for this pair in the selected range.")
    else:
        rule = coins.RESAMPLE_RULES[interval]
        if rule is None and len(candles) > MAX_POINTS:
            rule, interval = "1D", "1d"
            st.caption("Too many hourly candles for this range, showing daily candles instead.")
        view = coins.resample_candles(candles, rule)

        first, last = view.iloc[0], view.iloc[-1]
        change = last["close"] / first["open"] - 1 if first["open"] else None
        up = change is not None and change >= 0
        color = "#16c784" if up else "#ea3943"
        arrow = "▲" if up else "▼"
        change_txt = "-" if change is None else f"{abs(change) * 100:,.2f}%"
        st.markdown(
            f"<div style='display:flex;align-items:baseline;gap:.75rem;flex-wrap:wrap'>"
            f"<span style='font-size:2.2rem;font-weight:700'>${last['close']:,.2f}</span>"
            f"<span style='font-size:1.2rem;font-weight:600;color:{color}'>{arrow} {change_txt}</span>"
            f"<span style='opacity:.7'>({lookback_label})</span></div>",
            unsafe_allow_html=True,
        )
        st.caption(
            f"{symbol} · range high \\${view['high'].max():,.2f} · low \\${view['low'].min():,.2f} · "
            f"from {first['timestamp']:%Y-%m-%d %H:%M} to {last['timestamp']:%Y-%m-%d %H:%M} UTC"
        )

        t1, t2, t3, t4 = st.columns(4)
        ema = t1.toggle("EMA200", True)
        rsi = t2.toggle("RSI", True)
        macd = t3.toggle("MACD", False)
        score = t4.toggle("Score", True)
        st.plotly_chart(charts.price_chart(view, symbol, ema, rsi, macd, score), width="stretch")

with st.expander("🪙 Coin overview", expanded=True):
    window_label = st.radio("Window", list(coins.WINDOWS), horizontal=True)
    overview = queries.overview(coins.WINDOWS[window_label])
    st.caption(f"change_pct = price change over the last {window_label}. Use 📋 to copy a row as JSON.")
    copyable_table(overview)

    row = overview[overview["symbol"] == symbol]
    if not row.empty:
        r = row.iloc[0]
        def num(v):
            return "-" if v is None or v != v else f"{v:.0f}"

        st.markdown(f"**{symbol} signals**")
        m1, m2, m3 = st.columns(3)
        m1.metric("Score", num(r["score"]), r["signal"] or None)
        m2.metric("RSI", num(r["rsi"]))
        m3.metric("Backtest vs hold", pct(r["backtest_vs_hold"]))

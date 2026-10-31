"""Plotly chart builders (phone-friendly heights, horizontal legends)."""

import plotly.graph_objects as go
from plotly.subplots import make_subplots

HEIGHT = 360
LAYOUT = dict(margin=dict(l=8, r=8, t=32, b=8), legend=dict(orientation="h", y=1.12), hovermode="x unified")


def _style(fig: go.Figure, height: int = HEIGHT) -> go.Figure:
    fig.update_layout(height=height, **LAYOUT)
    return fig


def price_chart(df, symbol: str, show_ema: bool, show_rsi: bool, show_macd: bool, show_score: bool) -> go.Figure:
    panels = [("price", 0.55)]
    if show_rsi:
        panels.append(("rsi", 0.15))
    if show_macd:
        panels.append(("macd", 0.15))
    if show_score:
        panels.append(("score", 0.15))
    total = sum(w for _, w in panels)
    fig = make_subplots(
        rows=len(panels), cols=1, shared_xaxes=True, vertical_spacing=0.03,
        row_heights=[w / total for _, w in panels],
    )
    row = {name: i + 1 for i, (name, _) in enumerate(panels)}
    fig.add_trace(
        go.Candlestick(
            x=df["timestamp"], open=df["open"], high=df["high"], low=df["low"], close=df["close"], name=symbol
        ),
        row=row["price"], col=1,
    )
    if show_ema and "ema_200" in df and df["ema_200"].notna().any():
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["ema_200"], name="EMA200", line=dict(width=1.5)), row=1, col=1)
    if show_rsi:
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["rsi_14"], name="RSI"), row=row["rsi"], col=1)
        fig.add_hline(y=70, line_dash="dot", row=row["rsi"], col=1)
        fig.add_hline(y=30, line_dash="dot", row=row["rsi"], col=1)
    if show_macd:
        fig.add_trace(go.Bar(x=df["timestamp"], y=df["macd_histogram"], name="MACD hist"), row=row["macd"], col=1)
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["macd"], name="MACD"), row=row["macd"], col=1)
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["macd_signal"], name="Signal"), row=row["macd"], col=1)
    if show_score:
        fig.add_trace(go.Scatter(x=df["timestamp"], y=df["technical_score"], name="Score"), row=row["score"], col=1)
        fig.add_hline(y=65, line_dash="dot", row=row["score"], col=1)
        fig.add_hline(y=35, line_dash="dot", row=row["score"], col=1)
    fig.update_xaxes(rangeslider_visible=False)
    return _style(fig, 300 + 110 * len(panels))


def equity_chart(curve) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=curve["timestamp"], y=curve["equity"], name="Strategy"))
    fig.add_trace(go.Scatter(x=curve["timestamp"], y=curve["benchmark_equity"], name="Buy & hold"))
    return _style(fig)


def drawdown_chart(curve) -> go.Figure:
    fig = go.Figure(go.Scatter(x=curve["timestamp"], y=curve["drawdown"], fill="tozeroy", name="Drawdown"))
    fig.update_yaxes(tickformat=".0%")
    return _style(fig, 240)


def bucket_chart(buckets) -> go.Figure:
    fig = go.Figure(go.Bar(x=buckets["bucket"], y=buckets["avg_forward_return"], name="Avg forward return"))
    fig.update_yaxes(tickformat=".2%")
    return _style(fig, 280)


def signal_chart(dist) -> go.Figure:
    fig = go.Figure()
    for sig in ("BUY", "HOLD", "AVOID"):
        if sig in dist:
            fig.add_trace(go.Bar(x=dist["symbol"], y=dist[sig], name=sig))
    fig.update_layout(barmode="stack")
    return _style(fig, 300)

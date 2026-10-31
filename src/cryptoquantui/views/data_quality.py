"""Data quality & refresh health."""

import streamlit as st

from cryptoquant.database.job_runs import JOB_ANALYTICS, JOB_BACKFILL, JOB_INGEST
from cryptoquantui import queries
from cryptoquantui.components.actions import job_button
from cryptoquantui.services import data_quality as dq

st.title("Data quality")
st.caption("Is the data fresh, complete and sane? Hourly candles; ingestion runs every 4h.")

bundle = queries.quality_bundle()
fresh, complete, integ, coverage = bundle["fresh"], bundle["complete"], bundle["integrity"], bundle["coverage"]
summary = dq.summarize(fresh, complete, integ)

c1, c2, c3 = st.columns(3)
c1.metric("Pairs fresh", f"{summary['fresh']}/{summary['pairs']}")
c2.metric("Need attention", summary["attention"])
c3.metric("Missing candles (24h)", summary["missing_24h"])
st.metric("Integrity issues", summary["integrity_issues"])

st.subheader("Freshness")
if fresh.empty:
    st.info("No tracked pairs found.")
else:
    view = fresh.assign(status=fresh["icon"] + " " + fresh["status"]).drop(columns=["icon"])
    st.dataframe(view, hide_index=True, use_container_width=True)

st.subheader("Completeness")
if not complete.empty:
    pivot = complete.pivot(index="symbol", columns="window_hours", values="pct_complete")
    pivot.columns = [f"{c}h %" for c in pivot.columns]
    st.dataframe(pivot, use_container_width=True)

with st.expander("Integrity checks (30 days)"):
    st.dataframe(integ, hide_index=True, use_container_width=True)

with st.expander("Analysis coverage (indicators & scores)"):
    st.dataframe(coverage, hide_index=True, use_container_width=True)

st.subheader("Gap explorer")
symbols = fresh["symbol"].tolist() if not fresh.empty else []
if symbols:
    symbol = st.selectbox("Pair", symbols, key="gap-symbol")
    gaps = dq.find_gaps(bundle["candles"], symbol)
    if gaps.empty:
        st.success("No gaps in the last 30 days.")
    else:
        st.dataframe(gaps, hide_index=True, use_container_width=True)

st.subheader("Actions")
job_button(JOB_INGEST)
job_button(JOB_ANALYTICS)
job_button(JOB_BACKFILL)

st.subheader("Job history")
if st.button("Refresh history", use_container_width=True):
    queries.job_runs.clear()
st.dataframe(queries.job_runs(), hide_index=True, use_container_width=True)

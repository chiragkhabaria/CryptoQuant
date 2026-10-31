"""CryptoQuant dashboard. Run: streamlit run src/cryptoquantui/app.py"""

import os

import streamlit as st

from cryptoquantui import jobs
from cryptoquantui.components import style

st.set_page_config(
    page_title="CryptoQuant", page_icon="📈", layout="wide", initial_sidebar_state="collapsed"
)
style.apply()


@st.cache_resource
def _start_worker() -> bool:
    jobs.ensure_worker_started()
    return True


if os.getenv("UI_EMBEDDED_WORKER", "1") != "0":
    _start_worker()

pages = [
    st.Page("views/coins.py", title="Coins", icon="🪙", default=True),
    st.Page("views/data_quality.py", title="Data quality", icon="🩺"),
    st.Page("views/backtests.py", title="Backtests & score", icon="🧪"),
]
st.navigation(pages).run()

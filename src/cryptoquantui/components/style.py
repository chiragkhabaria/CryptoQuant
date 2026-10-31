"""Mobile-friendly styling."""

import streamlit as st

CSS = """
<style>
.block-container { padding: 1rem 1rem 3rem; max-width: 1400px; }
[data-testid="stMetric"] { background: rgba(128,128,128,.08); border-radius: 8px; padding: .5rem .75rem; }
[data-testid="stMetricValue"] { font-size: 1.4rem; }
@media (max-width: 640px) {
  .block-container { padding: .5rem .5rem 3rem; }
  h1 { font-size: 1.5rem !important; }
  h2, h3 { font-size: 1.15rem !important; }
  [data-testid="stMetricValue"] { font-size: 1.15rem; }
  button { min-height: 2.75rem; }
}
</style>
"""


def apply() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def pct(value, digits: int = 1) -> str:
    return "-" if value is None or value != value else f"{value * 100:.{digits}f}%"

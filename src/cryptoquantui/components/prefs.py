"""Widget values that survive switching pages (Streamlit drops state of unrendered widgets)."""

import streamlit as st


def persisted(widget, label, key: str, default, options=None, **kwargs):
    """Render ``widget`` whose value is remembered in ``st.session_state['_prefs']``."""
    store = st.session_state.setdefault("_prefs", {})
    wkey = f"w_{key}"
    saved = store.get(key, default)
    if options is not None and saved not in options:
        saved = default if default in options else options[0]
    if wkey not in st.session_state:
        st.session_state[wkey] = saved

    def _save():
        store[key] = st.session_state[wkey]

    args = (label, options) if options is not None else (label,)
    value = widget(*args, key=wkey, on_change=_save, **kwargs)
    store[key] = value
    return value

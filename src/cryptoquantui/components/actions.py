"""Job action buttons with a two-step confirmation."""

import streamlit as st

from cryptoquantui import jobs, queries


def job_button(job_type: str, params: dict | None = None, label: str | None = None, key: str | None = None) -> None:
    label = label or jobs.JOB_LABELS[job_type]
    key = key or f"job-{job_type}"
    confirm_key = f"{key}-confirm"

    if not st.session_state.get(confirm_key):
        if st.button(label, key=key, use_container_width=True):
            st.session_state[confirm_key] = True
            st.rerun()
        return

    st.warning(f"Run **{label}** now?")
    yes, no = st.columns(2)
    if yes.button("Confirm", key=f"{key}-yes", type="primary", use_container_width=True):
        st.session_state[confirm_key] = False
        run_id = jobs.submit(job_type, params)
        queries.job_runs.clear()
        if run_id is None:
            st.info(f"{label} is already queued or running.")
        else:
            st.success(f"Queued (run #{run_id}). Track it in the history below.")
    if no.button("Cancel", key=f"{key}-no", use_container_width=True):
        st.session_state[confirm_key] = False
        st.rerun()

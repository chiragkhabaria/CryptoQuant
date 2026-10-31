"""Smoke tests: every dashboard page renders without exceptions."""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from tests.unit.test_ui_services import session, session_factory  # noqa: E402,F401

PAGES = ["coins", "data_quality", "backtests"]
VIEWS = Path(__file__).resolve().parents[2] / "src" / "cryptoquantui" / "views"


@pytest.mark.parametrize("page", PAGES)
def test_page_renders(page, session_factory, session, monkeypatch):
    monkeypatch.setattr("cryptoquantui.queries.get_session", session_factory)
    monkeypatch.setattr("cryptoquantui.jobs.get_session", session_factory)
    at = AppTest.from_file(str(VIEWS / f"{page}.py"), default_timeout=30)
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def test_persisted_widget_survives_not_being_rendered():
    def script():
        import streamlit as st

        from cryptoquantui.components.prefs import persisted

        if st.session_state.get("show", True):
            persisted(st.toggle, "RSI", "rsi", True)

    at = AppTest.from_function(script, default_timeout=30).run()
    at.toggle(key="w_rsi").set_value(False).run()
    at.session_state["show"] = False
    at.run()  # widget not rendered -> Streamlit drops its state
    at.session_state["show"] = True
    at.run()
    assert at.toggle(key="w_rsi").value is False

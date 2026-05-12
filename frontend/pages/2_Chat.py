"""Chat page — natural language revenue queries powered by the LLM backend."""

from __future__ import annotations

import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.api_client import APIClient
from utils import charts

st.set_page_config(
    page_title="Chat · Hotel Revenue",
    page_icon="💬",
    layout="wide",
)

if "api_client" not in st.session_state:
    st.session_state.api_client = APIClient()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

client: APIClient = st.session_state.api_client

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Chat")
    if st.button("Clear history", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()
    st.divider()
    st.caption("⚠️ Prototype · synthetic data only")

# ── Page header ───────────────────────────────────────────────────────────────

st.title("💬 Revenue Chat")
st.caption(
    "Ask questions about revenue, occupancy, competitors, or budget in plain English. "
    "The AI translates your question into SQL and returns the results."
)

# ── Suggested questions (shown only when chat is empty) ───────────────────────

SUGGESTED_QUESTIONS = [
    "What was our occupancy last month?",
    "Which channel brought the most revenue this quarter?",
    "How did we price against competitors during Iron Man Cascais?",
    "Are we on track to hit our budget this month?",
    "What is the average stay length for corporate guests?",
    "How much revenue came from events last month?",
    "What is our RevPAR trend year-over-year?",
    "Which room type performs best during events?",
]

if not st.session_state.chat_history:
    st.markdown("**Suggested questions — click to ask:**")
    col_a, col_b = st.columns(2)
    for i, question in enumerate(SUGGESTED_QUESTIONS):
        target_col = col_a if i % 2 == 0 else col_b
        if target_col.button(question, key=f"suggested_{i}", use_container_width=True):
            st.session_state._pending_query = question
            st.rerun()
    st.divider()

# ── Render existing chat history ──────────────────────────────────────────────

for message in st.session_state.chat_history:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.write(message["content"])
        else:
            _content = message["content"]
            st.write(_content["summary"])

            if _content.get("sql"):
                with st.expander("View generated SQL", expanded=False):
                    st.code(_content["sql"], language="sql")

            if _content.get("data"):
                df = pd.DataFrame(
                    _content["data"]["rows"],
                    columns=_content["data"]["columns"],
                )
                st.dataframe(df, use_container_width=True, hide_index=True)
                fig = charts.auto_chart(df)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)

# ── Query handler ─────────────────────────────────────────────────────────────

def _handle_query(query: str) -> None:
    """Append user message, call backend, render and store response."""
    st.session_state.chat_history.append({"role": "user", "content": query})

    with st.chat_message("user"):
        st.write(query)

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            response = client.chat(query, messages=st.session_state.chat_history)

        if response is None:
            summary = (
                "Sorry — the backend is not reachable. "
                "Please start the FastAPI server and try again."
            )
            st.warning(summary, icon="⚠️")
            st.session_state.chat_history.append(
                {"role": "assistant", "content": {"summary": summary, "sql": None, "data": None}}
            )
            return

        content = {
            "summary": response.get("summary", "Query completed."),
            "sql": response.get("sql"),
            "data": response.get("data"),
        }

        st.write(content["summary"])

        if content["sql"]:
            with st.expander("View generated SQL", expanded=False):
                st.code(content["sql"], language="sql")

        if content["data"]:
            df = pd.DataFrame(
                content["data"]["rows"],
                columns=content["data"]["columns"],
            )
            st.dataframe(df, use_container_width=True, hide_index=True)
            fig = charts.auto_chart(df)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

        st.session_state.chat_history.append({"role": "assistant", "content": content})


# Handle suggested-question button click (triggers a rerun with pending query)
if hasattr(st.session_state, "_pending_query"):
    pending = st.session_state._pending_query
    del st.session_state._pending_query
    _handle_query(pending)

# Chat input box at the bottom
if query := st.chat_input("Ask a revenue question…"):
    _handle_query(query)

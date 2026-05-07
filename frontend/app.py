"""Hotel Revenue Intelligence — Streamlit app entry point.

This is the home/landing page. Shared session state (API client, chat history)
is initialised here so it is available across all pages.
"""

from __future__ import annotations

import os
import sys

import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(__file__))

from utils.api_client import APIClient

load_dotenv()

st.set_page_config(
    page_title="Hotel Revenue Intelligence",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialise shared session state
if "api_client" not in st.session_state:
    st.session_state.api_client = APIClient()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ── Page content ──────────────────────────────────────────────────────────────

st.title("🏨 Hotel Revenue Intelligence")
st.caption("AI-driven revenue analysis for independent hotels · Prototype · Synthetic data")

backend_ok = st.session_state.api_client.health()

if backend_ok:
    st.success("Backend connected", icon="✅")
else:
    st.warning(
        "Backend not reachable — charts will be empty until the API is running. "
        "Start FastAPI at `http://localhost:8000` and refresh.",
        icon="⚠️",
    )

st.markdown("---")
st.markdown("Use the **sidebar** to navigate between views.")

col1, col2 = st.columns(2)

with col1:
    st.markdown(
        """
        ### 📊 Dashboard
        Live KPI metrics, revenue breakdowns by channel and segment,
        actual vs budget variance, and an events calendar for the selected period.
        """
    )

with col2:
    st.markdown(
        """
        ### 💬 Chat
        Ask revenue questions in plain English. The AI translates your question
        into SQL, runs it against the database, and returns a summary with
        the underlying data and an auto-generated chart.
        """
    )

st.markdown("---")
st.caption(
    "Prototype · 100-room 4-star hotel, Lisbon · 16 months synthetic data · "
    "Advanced ML — S2 T4"
)

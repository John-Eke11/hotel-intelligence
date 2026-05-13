"""Audit Log page — view executed SQL queries."""

from __future__ import annotations
import os
import streamlit as st

st.set_page_config(
    page_title="Audit Log",
    page_icon="📋",
    layout="wide",
)

st.title("📋 Query Audit Log")
st.caption("Post-deployment monitoring signal (AI Safety Case Field 6). Logs all executed backend queries.")

log_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "api", "audit.log"))

if st.button("Refresh Log"):
    st.rerun()

if os.path.exists(log_file_path):
    with open(log_file_path, "r", encoding="utf-8") as f:
        logs = f.readlines()
        
    if logs:
        st.code("".join(reversed(logs[-100:])), language="log")  # Show last 100 entries reversed
    else:
        st.info("Audit log is empty.")
else:
    st.warning("Audit log file not found. Queries will appear here once executed.")

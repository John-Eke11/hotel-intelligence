"""Dashboard page — KPI metrics, revenue charts, and budget variance."""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.api_client import APIClient
from utils import charts

st.set_page_config(
    page_title="Dashboard · Hotel Revenue",
    page_icon="📊",
    layout="wide",
)

if "api_client" not in st.session_state:
    st.session_state.api_client = APIClient()

client: APIClient = st.session_state.api_client

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Filters")

    today = date.today()
    date_range = st.date_input(
        "Date range",
        value=(today - timedelta(days=30), today),
        max_value=today,
        format="DD/MM/YYYY",
    )

    # Guard against the transient single-date state while the user is picking
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        from_date, to_date = date_range[0], date_range[1]
    else:
        from_date, to_date = today - timedelta(days=30), today

    st.divider()
    st.caption("⚠️ Prototype · synthetic data only")

# ── Page header ───────────────────────────────────────────────────────────────

st.title("📊 Dashboard")
st.caption(
    f"{from_date.strftime('%d %b %Y')} – {to_date.strftime('%d %b %Y')} "
    f"· {(to_date - from_date).days} days"
)

# ── KPI cards ─────────────────────────────────────────────────────────────────

kpis = client.get_kpis(from_date, to_date)

col1, col2, col3, col4 = st.columns(4)

if kpis:
    col1.metric(
        "Occupancy",
        f"{kpis.get('occupancy', 0):.1%}",
        delta=f"{kpis.get('occupancy_delta', 0):+.1%}" if kpis.get("occupancy_delta") is not None else None,
    )
    col2.metric(
        "ADR",
        f"€{kpis.get('adr', 0):,.2f}",
        delta=f"€{kpis.get('adr_delta', 0):+.2f}" if kpis.get("adr_delta") is not None else None,
    )
    col3.metric(
        "RevPAR",
        f"€{kpis.get('revpar', 0):,.2f}",
        delta=f"€{kpis.get('revpar_delta', 0):+.2f}" if kpis.get("revpar_delta") is not None else None,
    )
    col4.metric(
        "TRevPAR",
        f"€{kpis.get('trevpar', 0):,.2f}",
        delta=f"€{kpis.get('trevpar_delta', 0):+.2f}" if kpis.get("trevpar_delta") is not None else None,
    )
else:
    for col, label in zip([col1, col2, col3, col4], ["Occupancy", "ADR", "RevPAR", "TRevPAR"]):
        col.metric(label, "—")
    st.info("KPI data unavailable — backend not connected.", icon="ℹ️")

st.divider()

# ── Revenue breakdowns ────────────────────────────────────────────────────────

col_ch, col_seg = st.columns(2)

with col_ch:
    st.subheader("Revenue by Channel")
    channel_data = client.get_revenue_by_channel(from_date, to_date)
    if channel_data:
        st.plotly_chart(
            charts.revenue_by_channel_chart(channel_data),
            use_container_width=True,
        )
    else:
        st.info("No channel data available.", icon="ℹ️")

with col_seg:
    st.subheader("Revenue by Segment")
    segment_data = client.get_revenue_by_segment(from_date, to_date)
    if segment_data:
        st.plotly_chart(
            charts.revenue_by_segment_chart(segment_data),
            use_container_width=True,
        )
    else:
        st.info("No segment data available.", icon="ℹ️")

st.divider()

# ── Monthly trend ─────────────────────────────────────────────────────────────

st.subheader("Monthly Revenue vs Budget")
trend_data = client.get_monthly_trend(from_date, to_date)
if trend_data:
    st.plotly_chart(
        charts.monthly_trend_chart(trend_data),
        use_container_width=True,
    )
else:
    st.info("No trend data available.", icon="ℹ️")

st.divider()

# ── Events in period ──────────────────────────────────────────────────────────

st.subheader("Events in Period")
st.caption("External demand drivers (sporting events, congresses, festivals) that affect market rates.")

events_data = client.get_events(from_date, to_date)
if events_data:
    df_events = pd.DataFrame(events_data)
    display_cols = {
        "event_name": "Event",
        "event_type": "Type",
        "event_start_date": "Start",
        "event_end_date": "End",
        "historical_rate_uplift": "Rate Uplift",
        "is_recurring": "Recurring",
    }
    df_events = df_events[[c for c in display_cols if c in df_events.columns]]
    df_events = df_events.rename(columns=display_cols)
    if "Rate Uplift" in df_events.columns:
        df_events["Rate Uplift"] = df_events["Rate Uplift"].apply(lambda x: f"+{x:.0%}")
    st.dataframe(df_events, use_container_width=True, hide_index=True)
else:
    st.info("No events data available.", icon="ℹ️")

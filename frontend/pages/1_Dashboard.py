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

# ── KPI card helpers ──────────────────────────────────────────────────────────

_KPI_CARD_CSS = """
<style>
.kpi-card {
    background: #ffffff;
    border: 1px solid #E2E8F0;
    border-radius: 10px;
    padding: 20px 22px 16px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
.kpi-label {
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #7A8899;
    margin: 0 0 8px 0;
}
.kpi-value {
    font-size: 1.9rem;
    font-weight: 700;
    color: #1C2B3A;
    line-height: 1;
    margin: 0 0 10px 0;
}
.kpi-delta-pos  { font-size: 0.78rem; font-weight: 600; color: #27AE60; margin: 0; }
.kpi-delta-neg  { font-size: 0.78rem; font-weight: 600; color: #E74C3C; margin: 0; }
.kpi-delta-none { font-size: 0.78rem; color: #B0BAC5;   margin: 0; }
.section-label {
    font-size: 0.70rem;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #7A8899;
    margin: 0 0 12px 0;
    padding-bottom: 10px;
    border-bottom: 1px solid #E2E8F0;
    display: block;
}
</style>
"""

def _kpi_card(label: str, value: str, delta: float | None, delta_fmt: str) -> str:
    if delta is None:
        delta_html = '<p class="kpi-delta-none">no comparison data</p>'
    elif delta >= 0:
        delta_html = f'<p class="kpi-delta-pos">&#9650; {delta_fmt} vs. prev. period</p>'
    else:
        delta_html = f'<p class="kpi-delta-neg">&#9660; {delta_fmt} vs. prev. period</p>'
    return (
        f'<div class="kpi-card">'
        f'<p class="kpi-label">{label}</p>'
        f'<p class="kpi-value">{value}</p>'
        f'{delta_html}'
        f'</div>'
    )


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

st.title("Dashboard")
st.caption(
    f"{from_date.strftime('%d %b %Y')} – {to_date.strftime('%d %b %Y')} "
    f"· {(to_date - from_date).days} days"
)

# ── KPI cards ─────────────────────────────────────────────────────────────────

st.markdown(_KPI_CARD_CSS, unsafe_allow_html=True)

kpis = client.get_kpis(from_date, to_date)

col1, col2, col3, col4 = st.columns(4)

if kpis:
    occ     = kpis.get("occupancy", 0)
    adr     = kpis.get("adr", 0)
    revpar  = kpis.get("revpar", 0)
    trevpar = kpis.get("trevpar", 0)
    occ_d     = kpis.get("occupancy_delta")
    adr_d     = kpis.get("adr_delta")
    revpar_d  = kpis.get("revpar_delta")
    trevpar_d = kpis.get("trevpar_delta")

    col1.markdown(_kpi_card("Occupancy", f"{occ:.1%}",       occ_d,     f"{abs(occ_d):.1%}"    if occ_d     is not None else ""), unsafe_allow_html=True)
    col2.markdown(_kpi_card("ADR",       f"€{adr:,.2f}",     adr_d,     f"€{abs(adr_d):.2f}"   if adr_d     is not None else ""), unsafe_allow_html=True)
    col3.markdown(_kpi_card("RevPAR",    f"€{revpar:,.2f}",  revpar_d,  f"€{abs(revpar_d):.2f}" if revpar_d  is not None else ""), unsafe_allow_html=True)
    col4.markdown(_kpi_card("TRevPAR",   f"€{trevpar:,.2f}", trevpar_d, f"€{abs(trevpar_d):.2f}" if trevpar_d is not None else ""), unsafe_allow_html=True)
else:
    for col, label in zip([col1, col2, col3, col4], ["Occupancy", "ADR", "RevPAR", "TRevPAR"]):
        col.markdown(_kpi_card(label, "—", None, ""), unsafe_allow_html=True)
    st.info("KPI data unavailable — backend not connected.")

st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)

# ── Revenue breakdowns ────────────────────────────────────────────────────────

col_ch, col_seg = st.columns(2, gap="medium")

with col_ch:
    with st.container(border=True):
        st.markdown('<p class="section-label">Revenue by Channel</p>', unsafe_allow_html=True)
        channel_data = client.get_revenue_by_channel(from_date, to_date)
        if channel_data:
            st.plotly_chart(charts.revenue_by_channel_chart(channel_data), use_container_width=True)
        else:
            st.info("No channel data available.")

with col_seg:
    with st.container(border=True):
        st.markdown('<p class="section-label">Revenue by Segment</p>', unsafe_allow_html=True)
        segment_data = client.get_revenue_by_segment(from_date, to_date)
        if segment_data:
            st.plotly_chart(charts.revenue_by_segment_chart(segment_data), use_container_width=True)
        else:
            st.info("No segment data available.")

# ── Monthly trend ─────────────────────────────────────────────────────────────

with st.container(border=True):
    st.markdown('<p class="section-label">Monthly Revenue vs Budget</p>', unsafe_allow_html=True)
    trend_data = client.get_monthly_trend(from_date, to_date)
    if trend_data:
        st.plotly_chart(charts.monthly_trend_chart(trend_data), use_container_width=True)
    else:
        st.info("No trend data available.")

# ── Events in period ──────────────────────────────────────────────────────────

_EVENT_TYPE_STYLE = {
    "sporting": "background-color: rgba(30,96,145,0.15);  color: #1E6091; font-weight: 600",
    "festival": "background-color: rgba(243,156,18,0.15); color: #c87f00; font-weight: 600",
    "congress": "background-color: rgba(162,59,114,0.15); color: #A23B72; font-weight: 600",
    "holiday":  "background-color: rgba(39,174,96,0.15);  color: #1e7e34; font-weight: 600",
}

with st.container(border=True):
    st.markdown('<p class="section-label">Events in Period</p>', unsafe_allow_html=True)
    st.caption("External demand drivers — sporting events, congresses, festivals — that affect market rates.")
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

        def _style_event_type(val):
            return _EVENT_TYPE_STYLE.get(str(val).lower(), "")

        styled = df_events.style.map(_style_event_type, subset=["Type"]) if "Type" in df_events.columns else df_events.style
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.info("No events data available.")

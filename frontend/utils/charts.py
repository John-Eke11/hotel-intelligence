"""Reusable Plotly chart builders for the Hotel Revenue Intelligence dashboard."""

from __future__ import annotations

from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


# Consistent colour palette across all charts
_BLUE = "#1E6091"
_CYAN = "#2E86AB"
_PURPLE = "#A23B72"
_GREEN = "#27AE60"
_ORANGE = "#F39C12"

_CHANNEL_COLORS = px.colors.qualitative.Set2
_SEGMENT_COLORS = [_BLUE, _PURPLE, _GREEN]


def revenue_by_channel_chart(data: list[dict]) -> go.Figure:
    """Horizontal bar chart of total revenue by booking channel."""
    df = pd.DataFrame(data).sort_values("total_revenue", ascending=True)
    fig = px.bar(
        df,
        x="total_revenue",
        y="channel",
        orientation="h",
        color="channel",
        color_discrete_sequence=_CHANNEL_COLORS,
        labels={"total_revenue": "Revenue (€)", "channel": ""},
        text_auto=".3s",
    )
    fig.update_layout(
        showlegend=False,
        margin=dict(l=0, r=16, t=8, b=0),
        height=280,
        xaxis_tickprefix="€",
    )
    return fig


def revenue_by_segment_chart(data: list[dict]) -> go.Figure:
    """Donut chart of revenue split by guest segment."""
    df = pd.DataFrame(data)
    fig = px.pie(
        df,
        names="segment",
        values="total_revenue",
        hole=0.48,
        color_discrete_sequence=_SEGMENT_COLORS,
    )
    fig.update_traces(textposition="outside", textinfo="percent+label")
    fig.update_layout(
        showlegend=False,
        margin=dict(l=0, r=0, t=8, b=8),
        height=280,
    )
    return fig


def monthly_trend_chart(data: list[dict]) -> go.Figure:
    """Line chart comparing actual vs target (budget) revenue by month."""
    df = pd.DataFrame(data)
    df["month"] = pd.to_datetime(df["month"])

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["month"],
            y=df["actual_revenue"],
            name="Actual",
            mode="lines+markers",
            line=dict(color=_BLUE, width=2.5),
            marker=dict(size=6),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["month"],
            y=df["target_revenue"],
            name="Budget",
            mode="lines+markers",
            line=dict(color=_ORANGE, width=2, dash="dash"),
            marker=dict(size=6),
        )
    )
    fig.update_layout(
        xaxis_title=None,
        yaxis_title="Revenue (€)",
        yaxis_tickprefix="€",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=0, r=0, t=32, b=0),
        height=300,
    )
    return fig


def auto_chart(df: pd.DataFrame) -> Optional[go.Figure]:
    """Best-effort chart inferred from a query result dataframe.

    Looks for one categorical column and one numeric column. Returns None when
    no sensible chart can be built so the caller can skip rendering.
    """
    if df.empty or len(df.columns) < 2:
        return None

    # Try to parse any string column that looks like a date
    for col in df.select_dtypes(include="object").columns:
        try:
            df[col] = pd.to_datetime(df[col])
        except (ValueError, TypeError):
            pass

    date_cols = df.select_dtypes(include="datetime64").columns.tolist()
    cat_cols = df.select_dtypes(include="object").columns.tolist()
    num_cols = df.select_dtypes(include="number").columns.tolist()

    if not num_cols:
        return None

    y_col = num_cols[0]

    # Time-series line chart
    if date_cols:
        x_col = date_cols[0]
        color_col = cat_cols[0] if cat_cols else None
        fig = px.line(
            df,
            x=x_col,
            y=y_col,
            color=color_col,
            color_discrete_sequence=[_BLUE, _PURPLE, _GREEN, _ORANGE],
        )
        fig.update_layout(margin=dict(l=0, r=0, t=8, b=0), height=300)
        return fig

    # Categorical bar chart (cap at 20 categories for readability)
    if cat_cols and df[cat_cols[0]].nunique() <= 20:
        x_col = cat_cols[0]
        fig = px.bar(
            df,
            x=x_col,
            y=y_col,
            color_discrete_sequence=[_BLUE],
        )
        fig.update_layout(margin=dict(l=0, r=0, t=8, b=0), height=300)
        return fig

    return None

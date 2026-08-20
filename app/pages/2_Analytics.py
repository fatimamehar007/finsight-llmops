"""Analytics — Trends, distributions, and CSV export."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import (
    HIGH_COLOR, LOW_COLOR, MED_COLOR,
    BORDER, TEXT, MUTED, NAVY,
    inject_css, render_sidebar,
)
from api_client import get_logs_as_df

st.set_page_config(
    page_title="Analytics | FinSight",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""<style>
[data-testid="collapsedControl"]{display:none !important;}
[data-testid="stSidebar"]{
    min-width:220px !important;
    background:#f8f8f6 !important;
    border-right:1px solid #e8e8e4 !important;
}
</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("**FinSight LLMOps**")
    st.caption("v1.0")
    st.divider()
    st.page_link("main.py", label="Home")
    st.page_link("pages/1_Query_Monitor.py", label="Inspector")
    st.page_link("pages/2_Analytics.py", label="Analytics")
    st.page_link("pages/3_Compliance_Report.py", label="Reports")
    st.divider()
    from utils import _ollama_status as _llm_online
    st.markdown("🟢 LLM Online" if _llm_online() else "🔴 LLM Offline")

inject_css()

# Sidebar — date range filter
with st.sidebar:
    st.markdown(
        f'<div style="border-top:1px solid {BORDER};margin:16px 0;"></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="font-size:12px;font-weight:600;color:{MUTED};'
        f'text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px;">'
        f'Date Range</div>',
        unsafe_allow_html=True,
    )
    today     = datetime.utcnow().date()
    date_from = st.date_input("From", value=today - timedelta(days=30), label_visibility="collapsed")
    date_to   = st.date_input("To",   value=today, label_visibility="collapsed")
    st.markdown(
        f'<div style="font-size:12px;color:{MUTED};margin-top:4px;">{date_from} — {date_to}</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Top bar
# ---------------------------------------------------------------------------
st.markdown(
    f'<div style="display:flex;justify-content:space-between;align-items:center;'
    f'padding:0 0 16px;border-bottom:1px solid {BORDER};margin-bottom:28px;">'
    f'<span style="font-size:12px;font-weight:500;text-transform:uppercase;'
    f'letter-spacing:.08em;color:{TEXT};">Analytics</span>'
    f'</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Load & filter
# ---------------------------------------------------------------------------
df = get_logs_as_df()

if df.empty:
    st.markdown(
        f'<div style="text-align:center;padding:64px 0;color:{MUTED};'
        f'border:1px solid {BORDER};border-radius:4px;">'
        f'<div style="font-size:14px;">No query data yet.</div>'
        f'<div style="font-size:13px;margin-top:8px;">Submit queries in Inspector first.</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if st.button("Go to Inspector"):
        st.switch_page("pages/1_Query_Monitor.py")
    st.stop()

df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
mask  = (df["timestamp"].dt.date >= date_from) & (df["timestamp"].dt.date <= date_to)
df_f  = df[mask].copy().sort_values("timestamp")

if df_f.empty:
    st.markdown(
        f'<div style="padding:24px 0;color:{MUTED};font-size:14px;">'
        f'No data in selected range. Adjust the date filter.</div>',
        unsafe_allow_html=True,
    )
    st.stop()

# Shared layout defaults
def _base(height=260):
    return dict(
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color=MUTED, size=11),
        height=height,
        margin=dict(t=8, b=8, l=0, r=0),
        showlegend=False,
    )

# ---------------------------------------------------------------------------
# 2 × 2 chart grid
# ---------------------------------------------------------------------------
row1_left, row1_right = st.columns(2, gap="large")

with row1_left:
    st.markdown(
        f'<div style="font-size:13px;font-weight:500;color:{TEXT};margin-bottom:12px;">'
        f'Risk Score Over Time</div>',
        unsafe_allow_html=True,
    )
    fig1 = px.line(
        df_f, x="timestamp", y="overall_risk_score",
        markers=True,
        color_discrete_sequence=[NAVY],
        labels={"overall_risk_score": "Risk Score", "timestamp": ""},
    )
    fig1.update_traces(
        hovertemplate="<b>%{x}</b><br>Risk Score: %{y:.1f}<extra></extra>",
        line=dict(width=1.5),
        marker=dict(size=5),
    )
    fig1.update_layout(
        **_base(),
        xaxis=dict(gridcolor=None, showline=False, zeroline=False),
        yaxis=dict(gridcolor="#f0f0f0", showline=False, zeroline=False, range=[0, 105]),
    )
    st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})

with row1_right:
    st.markdown(
        f'<div style="font-size:13px;font-weight:500;color:{TEXT};margin-bottom:12px;">'
        f'Queries by Category</div>',
        unsafe_allow_html=True,
    )
    cat = df_f["query_category"].value_counts().reset_index()
    cat.columns = ["Category", "Count"]
    cat["Category"] = cat["Category"].str.replace("_", " ").str.title()
    fig2 = px.bar(
        cat, x="Count", y="Category", orientation="h",
        color_discrete_sequence=[NAVY],
        labels={"Count": "", "Category": ""},
    )
    fig2.update_traces(
        hovertemplate="<b>%{y}</b><br>%{x} queries<extra></extra>",
    )
    fig2.update_layout(
        **_base(),
        xaxis=dict(gridcolor="#f0f0f0", showline=False, zeroline=False),
        yaxis=dict(gridcolor=None, showline=False, zeroline=False),
    )
    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

row2_left, row2_right = st.columns(2, gap="large")

with row2_left:
    st.markdown(
        f'<div style="font-size:13px;font-weight:500;color:{TEXT};margin-bottom:12px;">'
        f'Toxicity Over Time</div>',
        unsafe_allow_html=True,
    )
    fig3 = px.line(
        df_f, x="timestamp", y="toxicity_score",
        markers=True,
        color_discrete_sequence=[MED_COLOR],
        labels={"toxicity_score": "Toxicity", "timestamp": ""},
    )
    fig3.add_hline(
        y=0.5,
        line_dash="dash",
        line_color=HIGH_COLOR,
        annotation_text="Threshold 0.5",
        annotation_font_color=HIGH_COLOR,
        annotation_position="top right",
    )
    fig3.update_traces(
        hovertemplate="<b>%{x}</b><br>Toxicity: %{y:.4f}<extra></extra>",
        line=dict(width=1.5),
        marker=dict(size=5),
    )
    fig3.update_layout(
        **_base(),
        xaxis=dict(gridcolor=None, showline=False, zeroline=False),
        yaxis=dict(gridcolor="#f0f0f0", showline=False, zeroline=False),
    )
    st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

with row2_right:
    st.markdown(
        f'<div style="font-size:13px;font-weight:500;color:{TEXT};margin-bottom:12px;">'
        f'Safe vs Unsafe</div>',
        unsafe_allow_html=True,
    )
    safe_n   = int(df_f["is_safe"].sum())
    unsafe_n = len(df_f) - safe_n
    st.markdown(
        f'<div style="height:240px;display:flex;align-items:center;'
        f'justify-content:center;gap:48px;">'

        f'<div style="text-align:center;">'
        f'<div style="font-size:56px;font-weight:600;color:{LOW_COLOR};'
        f'letter-spacing:-0.02em;">{safe_n}</div>'
        f'<div style="font-size:11px;text-transform:uppercase;letter-spacing:.08em;'
        f'color:{MUTED};margin-top:6px;">Safe</div>'
        f'</div>'

        f'<div style="width:1px;height:64px;background:{BORDER};"></div>'

        f'<div style="text-align:center;">'
        f'<div style="font-size:56px;font-weight:600;color:{HIGH_COLOR};'
        f'letter-spacing:-0.02em;">{unsafe_n}</div>'
        f'<div style="font-size:11px;text-transform:uppercase;letter-spacing:.08em;'
        f'color:{MUTED};margin-top:6px;">Unsafe</div>'
        f'</div>'

        f'</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
st.markdown(
    f'<div style="border-top:1px solid {BORDER};margin:24px 0 16px;"></div>',
    unsafe_allow_html=True,
)
csv = df_f.to_csv(index=False).encode("utf-8")
st.download_button(
    label=f"↓ Export CSV  ({len(df_f)} rows, {date_from} – {date_to})",
    data=csv,
    file_name=f"finsight_{date_from}_{date_to}.csv",
    mime="text/csv",
)

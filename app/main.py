"""FinSight LLMOps — Overview dashboard."""

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    HIGH_COLOR, LOW_COLOR, MED_COLOR,
    BORDER, TEXT, MUTED, NAVY,
    inject_css, render_sidebar, _ollama_status,
)
from api_client import get_logs_as_df, get_summary_stats

st.set_page_config(
    page_title="FinSight LLMOps",
    page_icon="◈",
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

# ---------------------------------------------------------------------------
# Top bar
# ---------------------------------------------------------------------------
ok         = _ollama_status()
dot_color  = LOW_COLOR if ok else HIGH_COLOR
dot_char   = "●" if ok else "○"
status_str = "LLM Online" if ok else "LLM Offline"

st.markdown(
    f'<div style="display:flex;justify-content:space-between;align-items:center;'
    f'padding:0 0 16px;border-bottom:1px solid {BORDER};margin-bottom:28px;">'
    f'<span style="font-size:12px;font-weight:500;text-transform:uppercase;'
    f'letter-spacing:.08em;color:{TEXT};">FinSight LLMOps</span>'
    f'<span style="font-size:12px;color:{MUTED};">'
    f'<span style="color:{dot_color};">{dot_char}</span>&nbsp;{status_str}'
    f'</span></div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Newspaper metrics
# ---------------------------------------------------------------------------
stats     = get_summary_stats()
total     = stats["total_queries"]
avg_lat   = stats["avg_latency_ms"]
safe_pct  = stats["safe_response_pct"]
high_risk = stats["high_risk_flags"]

safe_c = LOW_COLOR if safe_pct >= 90 else (MED_COLOR if safe_pct >= 70 else HIGH_COLOR)
lat_c  = LOW_COLOR if avg_lat < 3000 else (MED_COLOR if avg_lat < 6000 else HIGH_COLOR)
hr_c   = LOW_COLOR if high_risk == 0 else (MED_COLOR if high_risk <= 2 else HIGH_COLOR)
avg_s  = avg_lat / 1000

st.markdown(
    f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;'
    f'border-top:2px solid {TEXT};padding:20px 0;gap:0;">'

    f'<div style="padding-right:32px;">'
    f'<div style="font-size:11px;font-weight:500;text-transform:uppercase;'
    f'letter-spacing:.08em;color:{MUTED};">Queries Logged</div>'
    f'<div style="font-size:36px;font-weight:600;color:{TEXT};'
    f'margin-top:8px;letter-spacing:-0.03em;">{total:,}</div>'
    f'</div>'

    f'<div style="padding:0 32px;border-left:1px solid {BORDER};">'
    f'<div style="font-size:11px;font-weight:500;text-transform:uppercase;'
    f'letter-spacing:.08em;color:{MUTED};">Avg Latency</div>'
    f'<div style="font-size:36px;font-weight:600;color:{lat_c};'
    f'margin-top:8px;letter-spacing:-0.03em;">{avg_s:.1f}s</div>'
    f'</div>'

    f'<div style="padding:0 32px;border-left:1px solid {BORDER};">'
    f'<div style="font-size:11px;font-weight:500;text-transform:uppercase;'
    f'letter-spacing:.08em;color:{MUTED};">Safe Rate</div>'
    f'<div style="font-size:36px;font-weight:600;color:{safe_c};'
    f'margin-top:8px;letter-spacing:-0.03em;">{safe_pct:.0f}%</div>'
    f'</div>'

    f'<div style="padding-left:32px;border-left:1px solid {BORDER};">'
    f'<div style="font-size:11px;font-weight:500;text-transform:uppercase;'
    f'letter-spacing:.08em;color:{MUTED};">High Risk</div>'
    f'<div style="font-size:36px;font-weight:600;color:{hr_c};'
    f'margin-top:8px;letter-spacing:-0.03em;">{high_risk}</div>'
    f'</div>'

    f'</div>'
    f'<div style="border-top:1px solid {BORDER};margin-bottom:32px;"></div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
df = get_logs_as_df()

# ---------------------------------------------------------------------------
# Recent queries — plain HTML table
# ---------------------------------------------------------------------------
st.markdown(
    f'<div style="font-size:13px;font-weight:600;color:{MUTED};'
    f'text-transform:uppercase;letter-spacing:.07em;'
    f'border-bottom:1px solid {BORDER};padding-bottom:8px;margin-bottom:16px;">'
    f'Recent Queries</div>',
    unsafe_allow_html=True,
)

if df.empty:
    st.markdown(
        f'<div style="padding:16px 0;color:{MUTED};font-size:14px;">'
        f'No queries logged yet.</div>',
        unsafe_allow_html=True,
    )
else:
    recent5 = df.tail(5).iloc[::-1].copy()

    _TH = (
        f'style="text-align:left;padding:8px 16px 8px 0;font-size:11px;'
        f'font-weight:500;text-transform:uppercase;letter-spacing:.08em;color:{MUTED};"'
    )
    rows = []
    for _, row in recent5.iterrows():
        level   = str(row.get("hallucination_risk", ""))
        r_color = HIGH_COLOR if level == "HIGH" else (MED_COLOR if level == "MEDIUM" else LOW_COLOR)
        r_label = {"LOW": "Low", "MEDIUM": "Medium", "HIGH": "High"}.get(level, level)
        q_str   = str(row["query"])
        q_trunc = q_str[:72] + ("…" if len(q_str) > 72 else "")
        time_s  = str(row["timestamp"])[:16]
        cat_s   = str(row.get("query_category", "—")).replace("_", " ").title()
        rows.append(
            f'<tr style="border-bottom:1px solid {BORDER};">'
            f'<td style="padding:8px 16px 8px 0;font-size:13px;color:{MUTED};white-space:nowrap;">{time_s}</td>'
            f'<td style="padding:8px 16px 8px 0;font-size:13px;">{q_trunc}</td>'
            f'<td style="padding:8px 16px 8px 0;font-size:13px;color:{MUTED};">{cat_s}</td>'
            f'<td style="padding:8px 0;font-size:13px;color:{r_color};font-weight:500;">{r_label}</td>'
            f'</tr>'
        )

    st.markdown(
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead><tr>'
        f'<th {_TH}>Time</th>'
        f'<th {_TH}>Query</th>'
        f'<th {_TH}>Category</th>'
        f'<th style="text-align:left;padding:8px 0;font-size:11px;font-weight:500;'
        f'text-transform:uppercase;letter-spacing:.08em;color:{MUTED};">Risk</th>'
        f'</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        f'</table>',
        unsafe_allow_html=True,
    )

st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Risk score — horizontal bar chart, last 10 queries
# ---------------------------------------------------------------------------
st.markdown(
    f'<div style="font-size:13px;font-weight:600;color:{MUTED};'
    f'text-transform:uppercase;letter-spacing:.07em;'
    f'border-bottom:1px solid {BORDER};padding-bottom:8px;margin-bottom:16px;">'
    f'Risk Score — Last 10 Queries</div>',
    unsafe_allow_html=True,
)

if df.empty:
    st.markdown(
        f'<div style="padding:16px 0;color:{MUTED};font-size:14px;">No data yet.</div>',
        unsafe_allow_html=True,
    )
else:
    recent10 = df.tail(10).copy()
    labels   = [f"Q{i + 1}" for i in range(len(recent10))]
    scores   = list(recent10["overall_risk_score"])
    colors   = [
        HIGH_COLOR if s >= 60 else (MED_COLOR if s >= 30 else LOW_COLOR)
        for s in scores
    ]

    fig = go.Figure(go.Bar(
        y=labels,
        x=scores,
        orientation="h",
        marker_color=colors,
        text=[f"{s:.0f}" for s in scores],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Risk Score: %{x:.1f}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(color=MUTED, size=11),
        height=320,
        margin=dict(t=4, b=4, l=40, r=60),
        xaxis=dict(
            range=[0, 115],
            gridcolor="#f0f0f0",
            gridwidth=1,
            showline=False,
            zeroline=False,
            tickfont=dict(color=MUTED, size=11),
            title=dict(text="Risk Score (0 – 100)", font=dict(color=MUTED, size=11)),
        ),
        yaxis=dict(
            gridcolor=None,
            showline=False,
            zeroline=False,
            tickfont=dict(color=MUTED, size=11),
        ),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

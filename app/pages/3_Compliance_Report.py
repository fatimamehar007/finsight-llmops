"""Reports — Compliance status and PDF audit report generation."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import (
    HIGH_COLOR, LOW_COLOR, MED_COLOR,
    BORDER, TEXT, MUTED, NAVY, BG_ALT,
    inject_css, render_sidebar,
)
from api_client import generate_compliance_pdf, get_logs_as_df

st.set_page_config(
    page_title="Reports | FinSight",
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
# Compliance logic
# ---------------------------------------------------------------------------
def _compliance(safe_pct: float, high_pct: float) -> tuple:
    """Return (verdict, color, description)."""
    if safe_pct > 90 and high_pct < 5:
        return "COMPLIANT", LOW_COLOR, "All key metrics within acceptable thresholds."
    elif safe_pct >= 70 and high_pct <= 20:
        return "REVIEW", MED_COLOR, "One or more metrics are outside recommended ranges."
    else:
        return "FAIL", HIGH_COLOR, "Critical thresholds breached. Immediate review required."


# ---------------------------------------------------------------------------
# Top bar
# ---------------------------------------------------------------------------
st.markdown(
    f'<div style="display:flex;justify-content:space-between;align-items:center;'
    f'padding:0 0 16px;border-bottom:1px solid {BORDER};margin-bottom:28px;">'
    f'<span style="font-size:12px;font-weight:500;text-transform:uppercase;'
    f'letter-spacing:.08em;color:{TEXT};">Reports</span>'
    f'</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
df_all = get_logs_as_df()
today  = datetime.utcnow().date()

# ---------------------------------------------------------------------------
# 40 / 60 split
# ---------------------------------------------------------------------------
form_col, preview_col = st.columns([2, 3], gap="large")

with form_col:
    st.markdown(
        f'<div style="font-size:13px;font-weight:500;color:{TEXT};'
        f'border-bottom:1px solid {BORDER};padding-bottom:8px;margin-bottom:16px;">'
        f'Report Configuration</div>',
        unsafe_allow_html=True,
    )
    report_title = st.text_input("Report Title",  value="Quarterly AI Risk Assessment")
    org_name     = st.text_input("Organization",  value="FinCorp Financial Technologies")
    analyst_name = st.text_input("Analyst Name",  value="AI Risk & Compliance Team")
    d1, d2 = st.columns(2)
    with d1:
        date_from_in = st.date_input("From", value=today - timedelta(days=30))
    with d2:
        date_to_in   = st.date_input("To",   value=today)
    st.markdown("<br>", unsafe_allow_html=True)
    generate_btn = st.button("Generate Report PDF", type="primary", use_container_width=True)

with preview_col:
    st.markdown(
        f'<div style="font-size:13px;font-weight:500;color:{TEXT};'
        f'border-bottom:1px solid {BORDER};padding-bottom:8px;margin-bottom:16px;">'
        f'Live Preview</div>',
        unsafe_allow_html=True,
    )

    if df_all.empty:
        st.markdown(
            f'<div style="color:{MUTED};font-size:14px;">No data available. Run queries first.</div>',
            unsafe_allow_html=True,
        )
        df_f = pd.DataFrame()
    else:
        df_all["timestamp"] = pd.to_datetime(df_all["timestamp"], utc=True)
        mask = (
            (df_all["timestamp"].dt.date >= date_from_in) &
            (df_all["timestamp"].dt.date <= date_to_in)
        )
        df_f = df_all[mask].copy()

    if not df_f.empty:
        total    = len(df_f)
        safe_pct = df_f["is_safe"].sum() / total * 100
        dist     = df_f["hallucination_risk"].value_counts().to_dict()
        high_ct  = dist.get("HIGH", 0)
        high_pct = high_ct / total * 100

        status, s_color, s_desc = _compliance(safe_pct, high_pct)

        # Compliance verdict — one large word
        st.markdown(
            f'<div style="margin:0 0 4px;">'
            f'<div style="font-size:10px;text-transform:uppercase;letter-spacing:.12em;'
            f'color:{MUTED};margin-bottom:10px;">Compliance Status</div>'
            f'<div style="font-size:44px;font-weight:700;color:{s_color};'
            f'letter-spacing:-0.02em;line-height:1;">{status}</div>'
            f'<div style="font-size:14px;color:#666;margin-top:10px;line-height:1.5;">{s_desc}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        safe_c = LOW_COLOR if safe_pct >= 90 else (MED_COLOR if safe_pct >= 70 else HIGH_COLOR)
        hc_c   = LOW_COLOR if high_ct == 0 else (MED_COLOR if high_ct <= 2 else HIGH_COLOR)

        # 3 plain numbers
        st.markdown(
            f'<div style="display:flex;gap:32px;margin:24px 0 0;'
            f'border-top:1px solid {BORDER};padding-top:20px;">'

            f'<div><div style="font-size:11px;text-transform:uppercase;'
            f'letter-spacing:.08em;color:{MUTED};">Queries</div>'
            f'<div style="font-size:24px;font-weight:600;color:{TEXT};margin-top:4px;">{total}</div></div>'

            f'<div><div style="font-size:11px;text-transform:uppercase;'
            f'letter-spacing:.08em;color:{MUTED};">Safe Rate</div>'
            f'<div style="font-size:24px;font-weight:600;color:{safe_c};margin-top:4px;">{safe_pct:.0f}%</div></div>'

            f'<div><div style="font-size:11px;text-transform:uppercase;'
            f'letter-spacing:.08em;color:{MUTED};">High Risk</div>'
            f'<div style="font-size:24px;font-weight:600;color:{hc_c};margin-top:4px;">{high_ct}</div></div>'

            f'</div>',
            unsafe_allow_html=True,
        )

        # Risk breakdown rows
        st.markdown(
            f'<div style="margin-top:24px;">'
            f'<div style="font-size:11px;text-transform:uppercase;letter-spacing:.06em;'
            f'color:{MUTED};margin-bottom:10px;">Hallucination Risk</div>',
            unsafe_allow_html=True,
        )
        for level, lc in [("LOW", LOW_COLOR), ("MEDIUM", MED_COLOR), ("HIGH", HIGH_COLOR)]:
            cnt = dist.get(level, 0)
            pct = cnt / total * 100
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:12px;'
                f'padding:6px 0;border-bottom:1px solid {BORDER};">'
                f'<span style="font-size:13px;color:{MUTED};width:64px;">{level}</span>'
                f'<span style="font-size:13px;color:{lc};font-weight:600;width:24px;">{cnt}</span>'
                f'<span style="font-size:13px;color:{MUTED};">{pct:.1f}%</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    else:
        df_f = pd.DataFrame()
        st.markdown(
            f'<div style="color:{MUTED};font-size:14px;">No data in selected range.</div>',
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Generate & download
# ---------------------------------------------------------------------------
st.markdown(
    f'<div style="border-top:1px solid {BORDER};margin:24px 0;"></div>',
    unsafe_allow_html=True,
)

if generate_btn:
    if df_f.empty:
        st.markdown(
            f'<div style="font-size:14px;color:{HIGH_COLOR};padding:8px 0;">'
            f'No data in the selected date range. Adjust the dates and try again.</div>',
            unsafe_allow_html=True,
        )
    else:
        with st.spinner("Generating PDF…"):
            try:
                pdf_bytes = generate_compliance_pdf(
                    report_title=report_title,
                    org_name=org_name,
                    analyst_name=analyst_name,
                    date_from=datetime.combine(date_from_in, datetime.min.time()),
                    date_to=datetime.combine(date_to_in, datetime.min.time()),
                )
                fname = f"finsight_compliance_{date_from_in}_{date_to_in}.pdf"
                st.markdown(
                    f'<div style="font-size:13px;color:{MUTED};margin-bottom:8px;">'
                    f'Ready — {fname}&nbsp;&nbsp;·&nbsp;&nbsp;{len(df_f)} queries included</div>',
                    unsafe_allow_html=True,
                )
                st.download_button(
                    label="↓ Download PDF Report",
                    data=pdf_bytes,
                    file_name=fname,
                    mime="application/pdf",
                )
            except Exception as exc:
                st.markdown(
                    f'<div style="font-size:14px;color:{HIGH_COLOR};padding:8px 0;">'
                    f'Failed to generate report: {exc}</div>',
                    unsafe_allow_html=True,
                )

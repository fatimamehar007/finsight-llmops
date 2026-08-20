"""Inspector — Submit queries, view real-time Responsible AI scores."""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils import (
    HIGH_COLOR, LOW_COLOR, MED_COLOR,
    BORDER, TEXT, MUTED, NAVY, BG_ALT,
    inject_css, render_sidebar, _ollama_status,
    risk_color, risk_label,
)
from api_client import get_logs_as_df, ingest_file, rag_status, run_query

st.set_page_config(
    page_title="Inspector | FinSight",
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
    st.markdown("🟢 LLM Online" if _ollama_status() else "🔴 LLM Offline")

inject_css()

# ---------------------------------------------------------------------------
# Sidebar — RAG controls (appended after shared sidebar)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        f'<div style="border-top:1px solid {BORDER};margin:16px 0;"></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="font-size:12px;font-weight:600;color:{MUTED};'
        f'text-transform:uppercase;letter-spacing:.06em;margin-bottom:8px;">'
        f'Policy Document</div>',
        unsafe_allow_html=True,
    )

    rag = rag_status()
    rag_loaded = rag["loaded"]
    status_txt = "Loaded" if rag_loaded else "Not loaded"
    status_c   = LOW_COLOR if rag_loaded else MUTED
    st.markdown(
        f'<div style="font-size:13px;color:{status_c};margin-bottom:8px;">{status_txt}</div>',
        unsafe_allow_html=True,
    )

    default_policy = Path("data/fincorp_ai_policy.pdf")

    if default_policy.exists() and not rag_loaded:
        if st.button("Load Policy", use_container_width=True):
            with st.spinner("Ingesting…"):
                try:
                    n = ingest_file(default_policy.name, default_policy.read_bytes())["chunks_ingested"]
                    st.success(f"{n} chunks loaded.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed: {exc}")

    uploaded = st.file_uploader("Upload PDF", type=["pdf"], label_visibility="collapsed")
    if uploaded:
        with st.spinner("Ingesting…"):
            try:
                n = ingest_file(uploaded.name, uploaded.getbuffer().tobytes())["chunks_ingested"]
                st.success(f"{n} chunks loaded.")
            except Exception as exc:
                st.error(f"Failed: {exc}")

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
    f'letter-spacing:.08em;color:{TEXT};">Inspector</span>'
    f'<span style="font-size:12px;color:{MUTED};">'
    f'<span style="color:{dot_color};">{dot_char}</span>&nbsp;{status_str}'
    f'</span></div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "query_input" not in st.session_state:
    st.session_state.query_input = ""
if "last_result" not in st.session_state:
    st.session_state["last_result"] = None

# ---------------------------------------------------------------------------
# Example chip buttons (always visible above the input)
# ---------------------------------------------------------------------------
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Fraud detection thresholds", use_container_width=True):
        st.session_state.query_input = (
            "What are the fraud detection thresholds for international transactions?"
        )
        st.rerun()
with col2:
    if st.button("Biometric data storage", use_container_width=True):
        st.session_state.query_input = (
            "Can the organization store biometric data for identity verification?"
        )
        st.rerun()
with col3:
    if st.button("Approved credit models", use_container_width=True):
        st.session_state.query_input = (
            "What ML models are approved for credit scoring decisions?"
        )
        st.rerun()
st.markdown("<br>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Query input
# ---------------------------------------------------------------------------
st.markdown(
    f'<div style="font-size:11px;font-weight:500;text-transform:uppercase;'
    f'letter-spacing:.08em;color:{MUTED};margin-bottom:6px;">Financial Query</div>',
    unsafe_allow_html=True,
)
st.text_area(
    "query",
    key="query_input",
    placeholder="Ask a compliance or policy question…",
    height=96,
    label_visibility="collapsed",
)
user_query = st.session_state.query_input

ctl_left, ctl_right = st.columns([5, 1])
with ctl_left:
    use_rag = st.toggle("Ground in policy context (RAG)", value=True)
with ctl_right:
    run_btn = st.button(
        "Run",
        type="primary",
        use_container_width=True,
        disabled=not user_query.strip(),
    )

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------
if run_btn and user_query.strip():
    with st.spinner("Running query through FinSight API…"):
        try:
            result = run_query(user_query, use_rag=use_rag)
        except Exception as exc:
            st.error(f"API request failed: {exc}")
            result = None
    if result is not None:
        st.session_state["last_result"]    = result
        st.session_state["last_response"]  = result["response"]
        st.session_state["last_context"]   = result["context_used"]
        st.rerun()

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
result = st.session_state.get("last_result")

if result is not None:
    response_text = st.session_state.get("last_response", "")
    context       = st.session_state.get("last_context", "")

    tox        = result["toxicity_score"]
    is_safe    = result["is_safe"]
    hall_risk  = result["hallucination_risk"]
    hall_conf  = result["hallucination_confidence"]
    latency_ms = result["latency_ms"]
    risk_score = result["overall_risk_score"]

    r_color = risk_color(hall_risk)
    lat_s   = latency_ms / 1000

    st.markdown(
        f'<div style="border-top:1px solid {BORDER};margin:20px 0;"></div>',
        unsafe_allow_html=True,
    )

    # ── LLM Response ──
    st.markdown(
        f'<div style="font-size:11px;font-weight:500;text-transform:uppercase;'
        f'letter-spacing:.08em;color:{MUTED};margin-bottom:8px;">Response</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="background:{BG_ALT};border-left:3px solid {r_color};'
        f'padding:14px 18px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;'
        f'font-size:13px;line-height:1.75;color:{TEXT};margin-bottom:4px;">'
        f'{response_text}</div>',
        unsafe_allow_html=True,
    )

    if context:
        with st.expander("Policy context used (RAG)"):
            st.code(context, language=None)

    # ── Agent trace + guardrails verdicts ──
    trace = result.get("agent_trace") or []
    input_allowed = result.get("guardrails_input_allowed", True)
    facts_grounded = result.get("guardrails_facts_grounded")
    facts_score = result.get("guardrails_facts_score")

    badge_c = LOW_COLOR if input_allowed else HIGH_COLOR
    badge_txt = "Allowed" if input_allowed else "Blocked"
    if facts_grounded is None:
        facts_c, facts_txt = MUTED, "Not checked (no retrieved evidence)"
    elif facts_grounded:
        facts_c, facts_txt = LOW_COLOR, f"Grounded ({facts_score:.0%} confidence)"
    else:
        facts_c, facts_txt = HIGH_COLOR, f"Not grounded — withheld ({facts_score:.0%} confidence)"

    st.markdown(
        f'<div style="display:flex;gap:32px;padding:10px 0;margin-bottom:8px;font-size:12px;color:{MUTED};">'
        f'<span>NeMo Guardrails — Input: <b style="color:{badge_c};">{badge_txt}</b></span>'
        f'<span>NeMo Guardrails — Fact-check: <b style="color:{facts_c};">{facts_txt}</b></span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if trace:
        with st.expander(f"Agent tool trace ({len(trace)} step{'s' if len(trace) != 1 else ''})"):
            for i, step in enumerate(trace, 1):
                st.markdown(f"**{i}. `{step['tool']}`** — input: `{step['input']}`")
                st.code(str(step["output"])[:2000], language=None)

    # ── 3 plain numbers ──
    tox_c = HIGH_COLOR if tox >= 0.5 else (MED_COLOR if tox >= 0.3 else LOW_COLOR)

    st.markdown(
        f'<div style="display:flex;align-items:center;padding:20px 0;'
        f'border-top:1px solid {BORDER};border-bottom:1px solid {BORDER};margin:20px 0;">'

        f'<div style="flex:1;padding-right:32px;">'
        f'<div style="font-size:11px;font-weight:500;text-transform:uppercase;'
        f'letter-spacing:.08em;color:{MUTED};margin-bottom:6px;">Toxicity Score</div>'
        f'<div style="font-size:26px;font-weight:600;color:{tox_c};letter-spacing:-0.02em;">{tox:.3f}</div>'
        f'<div style="font-size:12px;color:{MUTED};margin-top:4px;">{"Unsafe" if not is_safe else "Safe"}</div>'
        f'</div>'

        f'<div style="width:1px;height:56px;background:{BORDER};flex-shrink:0;"></div>'

        f'<div style="flex:1;padding:0 32px;">'
        f'<div style="font-size:11px;font-weight:500;text-transform:uppercase;'
        f'letter-spacing:.08em;color:{MUTED};margin-bottom:6px;">Hallucination Risk</div>'
        f'<div style="font-size:26px;font-weight:600;color:{r_color};letter-spacing:-0.02em;">{risk_label(hall_risk)}</div>'
        f'<div style="font-size:12px;color:{MUTED};margin-top:4px;">{hall_conf:.0%} confidence</div>'
        f'</div>'

        f'<div style="width:1px;height:56px;background:{BORDER};flex-shrink:0;"></div>'

        f'<div style="flex:1;padding-left:32px;">'
        f'<div style="font-size:11px;font-weight:500;text-transform:uppercase;'
        f'letter-spacing:.08em;color:{MUTED};margin-bottom:6px;">Latency</div>'
        f'<div style="font-size:26px;font-weight:600;color:{TEXT};letter-spacing:-0.02em;">{lat_s:.2f}s</div>'
        f'<div style="font-size:12px;color:{MUTED};margin-top:4px;">end-to-end</div>'
        f'</div>'

        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Progress bar (replaces gauge) ──
    bar_pct = min(risk_score, 100)
    st.markdown(
        f'<div style="margin:20px 0;">'
        f'<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px;">'
        f'<span style="font-size:11px;font-weight:500;text-transform:uppercase;'
        f'letter-spacing:.08em;color:{MUTED};">Overall Risk Score</span>'
        f'<span style="font-size:32px;font-weight:600;color:{r_color};'
        f'letter-spacing:-0.03em;">{risk_score:.0f}</span>'
        f'</div>'
        f'<div style="height:6px;background:#f0f0ee;border-radius:1px;">'
        f'<div style="width:{bar_pct:.0f}%;height:100%;background:{r_color};border-radius:1px;"></div>'
        f'</div>'
        f'<div style="display:flex;justify-content:space-between;margin-top:6px;">'
        f'<span style="font-size:12px;color:#aaa;">0 — Safe</span>'
        f'<span style="font-size:12px;color:#aaa;">100 — Critical</span>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Safety assessment (plain text, left border only) ──
    parts = []
    if not is_safe:
        parts.append(
            f"Toxicity {tox:.3f} — above safe threshold (0.5). "
            "Flag for review before acting on this response."
        )
    if hall_risk == "LOW":
        parts.append(
            f"Hallucination low ({hall_conf:.0%} confidence). "
            "Response is grounded in policy context."
        )
    elif hall_risk == "MEDIUM":
        parts.append(
            f"Hallucination medium ({hall_conf:.0%} confidence). "
            "Some claims may not be verifiable against source material. Manual review recommended."
        )
    else:
        parts.append(
            f"Hallucination high ({hall_conf:.0%} confidence). "
            "Model may have refused or contradicted source material. Do not act on this response."
        )
    if risk_score < 30:
        parts.append(f"Risk score {risk_score:.0f}/100 — within acceptable bounds.")
    elif risk_score < 60:
        parts.append(f"Risk score {risk_score:.0f}/100 — review before production use.")
    else:
        parts.append(
            f"Risk score {risk_score:.0f}/100 — critical. "
            "Escalate per AI Governance Policy incident reporting procedure."
        )

    st.markdown(
        f'<div style="border-left:3px solid {r_color};'
        f'padding:12px 16px;margin:0 0 24px;background:{BG_ALT};">'
        f'<div style="font-size:14px;color:#444;line-height:1.7;">{"  ".join(parts)}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Recent queries table
# ---------------------------------------------------------------------------
st.markdown(
    f'<div style="font-size:13px;font-weight:600;color:{MUTED};'
    f'text-transform:uppercase;letter-spacing:.07em;'
    f'border-bottom:1px solid {BORDER};padding-bottom:8px;margin-bottom:16px;">'
    f'Recent Queries</div>',
    unsafe_allow_html=True,
)

df = get_logs_as_df()
if df.empty:
    st.markdown(
        f'<div style="padding:16px 0;color:{MUTED};font-size:14px;">No queries logged yet.</div>',
        unsafe_allow_html=True,
    )
else:
    recent = df.tail(10).iloc[::-1].copy()
    _TH = (
        f'style="text-align:left;padding:8px 16px 8px 0;font-size:11px;'
        f'font-weight:500;text-transform:uppercase;letter-spacing:.08em;color:{MUTED};"'
    )
    rows = []
    for _, row in recent.iterrows():
        level   = str(row.get("hallucination_risk", ""))
        rc      = HIGH_COLOR if level == "HIGH" else (MED_COLOR if level == "MEDIUM" else LOW_COLOR)
        rl      = {"LOW": "Low", "MEDIUM": "Medium", "HIGH": "High"}.get(level, level)
        q_str   = str(row["query"])
        q_trunc = q_str[:72] + ("…" if len(q_str) > 72 else "")
        time_s  = str(row["timestamp"])[:16]
        score_s = f'{row["overall_risk_score"]:.1f}'
        rows.append(
            f'<tr style="border-bottom:1px solid {BORDER};">'
            f'<td style="padding:7px 16px 7px 0;font-size:13px;color:{MUTED};white-space:nowrap;">{time_s}</td>'
            f'<td style="padding:7px 16px 7px 0;font-size:13px;">{q_trunc}</td>'
            f'<td style="padding:7px 16px 7px 0;font-size:13px;color:{rc};font-weight:500;">{rl}</td>'
            f'<td style="padding:7px 0;font-size:13px;color:{MUTED};">{score_s}</td>'
            f'</tr>'
        )
    st.markdown(
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead><tr>'
        f'<th {_TH}>Time</th>'
        f'<th {_TH}>Query</th>'
        f'<th {_TH}>Risk</th>'
        f'<th style="text-align:left;padding:8px 0;font-size:11px;font-weight:500;'
        f'text-transform:uppercase;letter-spacing:.08em;color:{MUTED};">Score</th>'
        f'</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody>'
        f'</table>',
        unsafe_allow_html=True,
    )

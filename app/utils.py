"""Shared design system: colors, CSS, sidebar, helpers."""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------
HIGH_COLOR = "#c0392b"
MED_COLOR  = "#d4860a"
LOW_COLOR  = "#1e7e4a"
NAVY       = "#1a1a2e"
TEXT       = "#1a1a1e"
MUTED      = "#888888"
BORDER     = "#e8e8e4"
BG         = "#ffffff"
BG_ALT     = "#f8f8f6"

RISK_COLORS = {"LOW": LOW_COLOR, "MEDIUM": MED_COLOR, "HIGH": HIGH_COLOR}
RISK_ICONS  = {"LOW": "✅", "MEDIUM": "⚠️", "HIGH": "🚨"}
RISK_EMOJI  = {"LOW": "LOW", "MEDIUM": "MEDIUM", "HIGH": "HIGH"}


def risk_color(level: str) -> str:
    return RISK_COLORS.get(level, MUTED)


def risk_label(level: str) -> str:
    return {"LOW": "Low", "MEDIUM": "Medium", "HIGH": "High"}.get(level, level or "—")


# ---------------------------------------------------------------------------
# Global CSS  (white, typographic, minimal — colors hardcoded to match tokens)
# ---------------------------------------------------------------------------
_CSS = """
<style>
/* === Foundation === */
* { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important; }
.stApp { background: #ffffff !important; }
[data-testid="stAppViewContainer"] > .main { background: #ffffff !important; }
[data-testid="stHeader"] { display: none !important; }
[data-testid="stSidebarNav"] { display: none !important; }
#MainMenu { display: none !important; }
footer { display: none !important; }
.block-container {
    padding-top: 28px !important;
    padding-left: 2.5rem !important;
    padding-right: 2.5rem !important;
    max-width: 1080px !important;
}

/* === Sidebar (always visible, fixed width, no collapse) === */
[data-testid="stSidebar"] {
    min-width: 220px !important;
    max-width: 220px !important;
    background-color: #f8f8f6 !important;
    border-right: 1px solid #e8e8e4 !important;
    transform: none !important;
    visibility: visible !important;
    display: flex !important;
}
[data-testid="stSidebar"] > div:first-child {
    background-color: #f8f8f6 !important;
    padding: 24px 18px 20px !important;
}
section[data-testid="stSidebarContent"] { background: #f8f8f6 !important; }
section[data-testid="stSidebar"] { background: #f8f8f6 !important; }
/* Hide sidebar collapse/expand toggle buttons */
[data-testid="stSidebarCollapseButton"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
/* Keep sidebar visible even when JS sets collapsed state */
[data-testid="stSidebar"][aria-expanded="false"] {
    margin-left: 0 !important;
    transform: none !important;
}

/* === Metrics === */
[data-testid="stMetricValue"] {
    font-size: 28px !important;
    font-weight: 600 !important;
    color: #1a1a1e !important;
    letter-spacing: -0.02em !important;
}
[data-testid="stMetricLabel"] {
    font-size: 11px !important;
    font-weight: 500 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    color: #888888 !important;
}
[data-testid="stMetricDelta"] { font-size: 12px !important; }

/* === Buttons (Issue 3: all dark navy) === */
.stButton > button {
    background-color: #1a1a2e !important;
    color: white !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 8px 24px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    letter-spacing: 0.02em !important;
    transition: background 0.15s !important;
    width: 100% !important;
}
.stButton > button:hover {
    background-color: #2d2d4e !important;
    color: white !important;
}
.stButton > button:active {
    background-color: #0f0f1a !important;
}

/* === Secondary buttons (chip/outlined style) === */
.stButton > button[kind="secondary"] {
    background: white !important;
    color: #1a1a2e !important;
    border: 1px solid #e8e8e4 !important;
    font-size: 12px !important;
    padding: 4px 14px !important;
    width: 100% !important;
    font-weight: 400 !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: #1a1a2e !important;
    background: white !important;
    color: #1a1a2e !important;
}

/* === Download Button (text-link style) === */
[data-testid="stDownloadButton"] > button {
    background: transparent !important;
    color: #1a1a2e !important;
    border: none !important;
    padding: 0 !important;
    font-size: 14px !important;
    font-weight: 400 !important;
    text-decoration: underline !important;
    text-underline-offset: 3px !important;
    box-shadow: none !important;
    border-radius: 0 !important;
    width: auto !important;
}
[data-testid="stDownloadButton"] > button:hover {
    color: #444 !important;
    background: transparent !important;
}

/* === Inputs === */
.stTextArea textarea {
    border: 1px solid #e8e8e4 !important;
    border-radius: 4px !important;
    font-size: 14px !important;
    line-height: 1.6 !important;
    background: #ffffff !important;
    color: #1a1a1e !important;
}
.stTextArea textarea:focus {
    border-color: #1a1a2e !important;
    box-shadow: 0 0 0 2px rgba(26,26,46,0.07) !important;
}
.stTextInput > div > div > input {
    border: 1px solid #e8e8e4 !important;
    border-radius: 4px !important;
    font-size: 14px !important;
    color: #1a1a1e !important;
    background: #ffffff !important;
}
.stDateInput > div > div > input {
    border: 1px solid #e8e8e4 !important;
    border-radius: 4px !important;
    font-size: 14px !important;
}

/* === Sidebar page links === */
[data-testid="stPageLink"] { padding: 2px 0 !important; margin: 0 !important; }
[data-testid="stPageLink"] > a {
    color: #666666 !important;
    font-size: 14px !important;
    font-weight: 400 !important;
    text-decoration: none !important;
    padding: 2px 0 !important;
    display: block !important;
}
[data-testid="stPageLink"] > a:hover { color: #1a1a1e !important; }
[data-testid="stPageLink"] svg { display: none !important; }
[data-testid="stPageLink"] p { margin: 0 !important; font-size: 14px !important; }

/* === Alerts === */
[data-testid="stAlert"] {
    background: #f8f8f6 !important;
    border: 1px solid #e8e8e4 !important;
    border-radius: 4px !important;
}
[data-testid="stAlert"] p { color: #1a1a1e !important; }

/* === Divider === */
hr { border: none !important; border-top: 1px solid #e8e8e4 !important; margin: 20px 0 !important; }

/* === Dataframe === */
[data-testid="stDataFrameResizable"] {
    border: 1px solid #e8e8e4 !important;
    border-radius: 4px !important;
}

/* === Expander === */
details {
    border: 1px solid #e8e8e4 !important;
    border-radius: 4px !important;
    background: #ffffff !important;
}
summary {
    font-size: 13px !important;
    font-weight: 500 !important;
    color: #1a1a1e !important;
    padding: 8px 12px !important;
}
summary:hover { background: #f8f8f6 !important; }

/* === Toggle === */
.stToggle p { font-size: 14px !important; color: #1a1a1e !important; }
</style>
"""


def inject_css() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Section heading helper
# ---------------------------------------------------------------------------

def sh(title: str) -> None:
    st.markdown(
        f'<div style="font-size:13px;font-weight:600;color:{MUTED};'
        f'text-transform:uppercase;letter-spacing:.07em;'
        f'border-bottom:1px solid {BORDER};padding-bottom:8px;'
        f'margin:4px 0 16px;">{title}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# LLM status (cached 30 s)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30, show_spinner=False)
def _ollama_status() -> bool:
    from api_client import health
    return bool(health().get("ollama_online"))


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

_NAV = [
    ("home",      "main.py",                     "Overview"),
    ("inspector", "pages/1_Query_Monitor.py",     "Inspector"),
    ("analytics", "pages/2_Analytics.py",         "Analytics"),
    ("reports",   "pages/3_Compliance_Report.py", "Reports"),
]


_HR = '<div style="border-top:1px solid #e8e8e4;margin:14px 0;"></div>'


def render_sidebar(active: str = "") -> None:
    ok         = _ollama_status()
    dot_color  = "#1e7e4a" if ok else "#888888"
    dot        = "&#9679;" if ok else "&#9675;"
    status_str = "LLM Online" if ok else "LLM Offline"

    with st.sidebar:
        # App name + version
        st.markdown(
            '<div style="font-size:15px;font-weight:700;color:#1a1a1e;margin-bottom:3px;">'
            'FinSight LLMOps</div>'
            '<div style="font-size:11px;color:#888;">v1.0</div>',
            unsafe_allow_html=True,
        )
        st.markdown(_HR, unsafe_allow_html=True)

        # Navigation header
        st.markdown(
            '<div style="font-size:10px;font-weight:600;text-transform:uppercase;'
            'letter-spacing:.1em;color:#888;margin-bottom:8px;">Navigation</div>',
            unsafe_allow_html=True,
        )

        for key, path, label in _NAV:
            if key == active:
                st.markdown(
                    f'<div style="font-size:14px;font-weight:700;color:#1a1a2e;'
                    f'padding:3px 0;margin:1px 0;">{label}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.page_link(path, label=label)

        st.markdown(_HR, unsafe_allow_html=True)

        # LLM status
        st.markdown(
            f'<div style="font-size:13px;color:#555;">'
            f'<span style="color:{dot_color};">{dot}</span>&nbsp;{status_str}</div>',
            unsafe_allow_html=True,
        )

        st.markdown(_HR, unsafe_allow_html=True)

        # Footer
        st.markdown(
            '<div style="font-size:10px;color:#aaa;">AI Observability Platform</div>',
            unsafe_allow_html=True,
        )

"""Thin HTTP client for the FinSight REST API.

The Streamlit frontend never imports `backend/*` directly — every piece of
business logic (LLM calls, RAG, scoring, persistence, PDF generation) lives
behind this API boundary so the UI and the service can scale and deploy
independently.
"""

import os
from datetime import datetime

import httpx
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

_LOG_COLUMNS = [
    "id", "timestamp", "query", "response", "context_used",
    "toxicity_score", "is_safe", "hallucination_risk",
    "hallucination_confidence", "query_category",
    "latency_ms", "overall_risk_score",
]


def _client(timeout: float = 10.0) -> httpx.Client:
    return httpx.Client(base_url=API_BASE_URL, timeout=timeout)


def health() -> dict:
    """Return API/Ollama/RAG health, or an offline stub if the API is unreachable."""
    try:
        with _client(timeout=3.0) as c:
            resp = c.get("/health")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return {"status": "offline", "ollama_online": False, "rag_loaded": False}


def api_online() -> bool:
    return health().get("status") == "ok"


def run_query(query: str, use_rag: bool = True) -> dict:
    # Generous timeout: the agentic pipeline is several sequential LLM calls
    # (ReAct reasoning steps + 2 guardrail checks), and CPU-only Ollama
    # deployments (e.g. Azure Container Apps without a GPU workload profile)
    # are much slower per call than local GPU/Apple-silicon inference.
    with _client(timeout=600.0) as c:
        resp = c.post("/query", json={"query": query, "use_rag": use_rag})
        resp.raise_for_status()
        return resp.json()


def rag_status() -> dict:
    try:
        with _client() as c:
            resp = c.get("/rag/status")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return {"loaded": False, "document_count": 0}


def ingest_file(filename: str, content: bytes) -> dict:
    with _client(timeout=120.0) as c:
        resp = c.post("/ingest", files={"file": (filename, content, "application/pdf")})
        resp.raise_for_status()
        return resp.json()


def ingest_path(path: str) -> dict:
    with _client(timeout=120.0) as c:
        resp = c.post("/ingest/path", json={"path": path})
        resp.raise_for_status()
        return resp.json()


def get_logs_as_df() -> pd.DataFrame:
    try:
        with _client() as c:
            resp = c.get("/logs")
            resp.raise_for_status()
            records = resp.json()
    except Exception:
        records = []

    if not records:
        return pd.DataFrame(columns=_LOG_COLUMNS)

    df = pd.DataFrame(records)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def get_summary_stats() -> dict:
    try:
        with _client() as c:
            resp = c.get("/stats")
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return {
            "total_queries": 0,
            "avg_latency_ms": 0.0,
            "safe_response_pct": 0.0,
            "high_risk_flags": 0,
            "hallucination_distribution": {},
            "top_categories": [],
        }


def generate_compliance_pdf(
    report_title: str,
    org_name: str,
    analyst_name: str,
    date_from: datetime,
    date_to: datetime,
) -> bytes:
    with _client(timeout=60.0) as c:
        resp = c.post(
            "/reports/compliance",
            json={
                "report_title": report_title,
                "org_name": org_name,
                "analyst_name": analyst_name,
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
            },
        )
        resp.raise_for_status()
        return resp.content

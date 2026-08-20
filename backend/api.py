"""FinSight REST API — the only thing that talks to Ollama, ChromaDB, and the audit DB.

The Streamlit frontend is a pure HTTP client of this service. Run standalone with:
    uvicorn backend.api:app --host 0.0.0.0 --port 8000
"""

import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from backend import agent, database, guardrails_engine, llm_runner, rag_engine, reports, scorers

app = FastAPI(title="FinSight LLMOps API", version="1.0")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    query: str
    use_rag: bool = True


class QueryResponse(BaseModel):
    query: str
    response: str
    context_used: str
    toxicity_score: float
    is_safe: bool
    hallucination_risk: str
    hallucination_confidence: float
    query_category: str
    latency_ms: float
    overall_risk_score: float
    agent_trace: list[dict] = []
    guardrails_input_allowed: bool = True
    guardrails_facts_grounded: Optional[bool] = None
    guardrails_facts_score: Optional[float] = None


class RagStatus(BaseModel):
    loaded: bool
    document_count: int


class HealthStatus(BaseModel):
    status: str
    ollama_online: bool
    rag_loaded: bool


class IngestPathRequest(BaseModel):
    path: str


class ReportRequest(BaseModel):
    report_title: str = "Quarterly AI Risk Assessment"
    org_name: str = "FinCorp Financial Technologies"
    analyst_name: str = "AI Risk & Compliance Team"
    date_from: datetime
    date_to: datetime


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    return HealthStatus(
        status="ok",
        ollama_online=llm_runner.check_ollama_status(),
        rag_loaded=rag_engine.check_if_loaded(),
    )


# ---------------------------------------------------------------------------
# Query pipeline — agentic RAG (backend/agent.py) gated by NeMo Guardrails
# (backend/guardrails_engine.py) on both ends: an input safety check before
# the agent runs, and a fact-check of its answer against whatever policy
# context it retrieved, to catch and withhold ungrounded (hallucinated)
# answers before they reach the user.
# ---------------------------------------------------------------------------

@app.post("/query", response_model=QueryResponse)
def run_query(req: QueryRequest) -> QueryResponse:
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    input_check = guardrails_engine.check_input(req.query)
    if not input_check["allowed"]:
        response_text = (
            "This request was blocked by NeMo Guardrails input safety checks — it "
            "appears to violate the acceptable-use policy for this assistant."
        )
        scored = scorers.run_all_scorers(req.query, response_text, "", 0.0)
        scored["is_safe"] = False
        scored["toxicity_score"] = max(scored["toxicity_score"], 0.9)
        scored["overall_risk_score"] = max(scored["overall_risk_score"], 90.0)
        database.log_query(scored)
        return QueryResponse(**scored, agent_trace=[], guardrails_input_allowed=False)

    result = agent.run_agent(req.query, use_rag=req.use_rag)
    response_text = result["response"]
    evidence = result["evidence"]

    facts_check = guardrails_engine.check_facts(evidence, response_text)
    if evidence and not facts_check["grounded"]:
        response_text = (
            "The agent's draft answer could not be verified against the retrieved "
            "policy context, so NeMo Guardrails withheld it to prevent a possible "
            "hallucination. Please consult a compliance officer directly."
        )

    scored = scorers.run_all_scorers(req.query, response_text, evidence, result["latency_seconds"])
    if evidence and not facts_check["grounded"]:
        scored["hallucination_risk"] = "HIGH"
        scored["hallucination_confidence"] = max(scored["hallucination_confidence"], 0.9)
        scored["overall_risk_score"] = max(scored["overall_risk_score"], 80.0)

    database.log_query(scored)
    return QueryResponse(
        **scored,
        agent_trace=result["trace"],
        guardrails_input_allowed=True,
        guardrails_facts_grounded=facts_check.get("grounded") if evidence else None,
        guardrails_facts_score=facts_check.get("score"),
    )


# ---------------------------------------------------------------------------
# RAG ingestion
# ---------------------------------------------------------------------------

@app.get("/rag/status", response_model=RagStatus)
def rag_status() -> RagStatus:
    return RagStatus(
        loaded=rag_engine.check_if_loaded(),
        document_count=rag_engine.get_document_count(),
    )


@app.post("/ingest", response_model=dict)
async def ingest(file: UploadFile) -> dict:
    suffix = Path(file.filename or "upload.pdf").suffix or ".pdf"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        n = rag_engine.ingest_document(tmp_path)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    return {"chunks_ingested": n}


@app.post("/ingest/path", response_model=dict)
def ingest_path(req: IngestPathRequest) -> dict:
    """Ingest a PDF already present on the API container's filesystem (e.g. bundled demo policy)."""
    if not Path(req.path).exists():
        raise HTTPException(status_code=404, detail=f"{req.path} not found")
    try:
        n = rag_engine.ingest_document(req.path)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"chunks_ingested": n}


# ---------------------------------------------------------------------------
# Logs & stats
# ---------------------------------------------------------------------------

@app.get("/logs", response_model=list[dict])
def get_logs() -> list[dict]:
    df = database.get_logs_as_df()
    if df.empty:
        return []
    df = df.copy()
    df["timestamp"] = df["timestamp"].astype(str)
    return df.to_dict(orient="records")


@app.get("/stats", response_model=dict)
def get_stats() -> dict:
    return database.get_summary_stats()


# ---------------------------------------------------------------------------
# Compliance reports
# ---------------------------------------------------------------------------

@app.post("/reports/compliance")
def generate_compliance_report(req: ReportRequest) -> Response:
    df = database.get_logs_as_df()
    if df.empty:
        raise HTTPException(status_code=404, detail="No query data available for report generation")

    import pandas as pd

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    mask = (
        (df["timestamp"].dt.date >= req.date_from.date())
        & (df["timestamp"].dt.date <= req.date_to.date())
    )
    df_f = df[mask].copy()
    if df_f.empty:
        raise HTTPException(status_code=404, detail="No data in the selected date range")

    pdf_bytes = reports.generate_compliance_pdf(
        report_title=req.report_title,
        analyst_name=req.analyst_name,
        org_name=req.org_name,
        date_from=req.date_from,
        date_to=req.date_to,
        df=df_f,
    )
    fname = f"finsight_compliance_{req.date_from.date()}_{req.date_to.date()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )

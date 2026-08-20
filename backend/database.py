"""SQLAlchemy ORM layer for logging LLM queries and Responsible AI scores."""

import os
from datetime import datetime, timezone

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./finsight.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    query = Column(String, nullable=False)
    response = Column(String, nullable=False)
    context_used = Column(String, default="")
    toxicity_score = Column(Float, default=0.0)
    is_safe = Column(Boolean, default=True)
    hallucination_risk = Column(String, default="LOW")   # LOW / MEDIUM / HIGH
    hallucination_confidence = Column(Float, default=0.0)
    query_category = Column(String, default="general financial")
    latency_ms = Column(Float, default=0.0)
    overall_risk_score = Column(Float, default=0.0)      # 0–100


Base.metadata.create_all(bind=engine)


def log_query(data: dict) -> QueryLog:
    """Persist a scored query result to the database."""
    with SessionLocal() as session:
        record = QueryLog(
            query=data.get("query", ""),
            response=data.get("response", ""),
            context_used=data.get("context_used", ""),
            toxicity_score=data.get("toxicity_score", 0.0),
            is_safe=data.get("is_safe", True),
            hallucination_risk=data.get("hallucination_risk", "LOW"),
            hallucination_confidence=data.get("hallucination_confidence", 0.0),
            query_category=data.get("query_category", "general financial"),
            latency_ms=data.get("latency_ms", 0.0),
            overall_risk_score=data.get("overall_risk_score", 0.0),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def get_all_logs() -> list[QueryLog]:
    """Return all query logs ordered by most recent first."""
    with SessionLocal() as session:
        return session.query(QueryLog).order_by(QueryLog.timestamp.desc()).all()


def get_logs_as_df() -> pd.DataFrame:
    """Return all logs as a Pandas DataFrame for analytics."""
    with SessionLocal() as session:
        rows = session.query(QueryLog).order_by(QueryLog.timestamp.asc()).all()
        if not rows:
            return pd.DataFrame(columns=[
                "id", "timestamp", "query", "response", "context_used",
                "toxicity_score", "is_safe", "hallucination_risk",
                "hallucination_confidence", "query_category",
                "latency_ms", "overall_risk_score",
            ])
        return pd.DataFrame([
            {
                "id": r.id,
                "timestamp": r.timestamp,
                "query": r.query,
                "response": r.response,
                "context_used": r.context_used,
                "toxicity_score": r.toxicity_score,
                "is_safe": r.is_safe,
                "hallucination_risk": r.hallucination_risk,
                "hallucination_confidence": r.hallucination_confidence,
                "query_category": r.query_category,
                "latency_ms": r.latency_ms,
                "overall_risk_score": r.overall_risk_score,
            }
            for r in rows
        ])


def get_summary_stats() -> dict:
    """Aggregate KPIs for the homepage metrics panel."""
    with SessionLocal() as session:
        total = session.query(func.count(QueryLog.id)).scalar() or 0
        avg_latency = session.query(func.avg(QueryLog.latency_ms)).scalar() or 0.0
        safe_count = session.query(func.count(QueryLog.id)).filter(QueryLog.is_safe == True).scalar() or 0  # noqa: E712
        safe_pct = round((safe_count / total * 100), 1) if total else 0.0
        high_risk_count = (
            session.query(func.count(QueryLog.id))
            .filter(QueryLog.hallucination_risk == "HIGH")
            .scalar()
            or 0
        )

        risk_dist_rows = (
            session.query(QueryLog.hallucination_risk, func.count(QueryLog.id))
            .group_by(QueryLog.hallucination_risk)
            .all()
        )
        hallucination_distribution = {r: c for r, c in risk_dist_rows}

        category_rows = (
            session.query(QueryLog.query_category, func.count(QueryLog.id))
            .group_by(QueryLog.query_category)
            .order_by(func.count(QueryLog.id).desc())
            .all()
        )
        top_categories = [{"category": cat, "count": cnt} for cat, cnt in category_rows]

    return {
        "total_queries": total,
        "avg_latency_ms": round(avg_latency, 1),
        "safe_response_pct": safe_pct,
        "high_risk_flags": high_risk_count,
        "hallucination_distribution": hallucination_distribution,
        "top_categories": top_categories,
    }

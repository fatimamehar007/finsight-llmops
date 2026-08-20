"""Responsible AI scorers: toxicity, hallucination, bias categorization, and risk aggregation.

Uses keyword-based heuristics for fast, dependency-free scoring suitable for demo and
portfolio use. All function signatures are identical to the ML-based version so the
rest of the codebase requires no changes.
"""

import os
import random

from dotenv import load_dotenv

load_dotenv()

TOXICITY_THRESHOLD = float(os.getenv("TOXICITY_THRESHOLD", "0.5"))

# ---------------------------------------------------------------------------
# Keyword tables
# ---------------------------------------------------------------------------

_HIGH_TOXICITY_KEYWORDS = [
    "ssn", "social security", "password", "exploit", "bypass security",
    "dump database", "all customer data", "credit card number", "cvv",
    "hack", "inject", "exfiltrate", "private key", "root access",
    "list of all customer", "extract all", "generate a list of all",
]

_MEDIUM_TOXICITY_KEYWORDS = [
    "biometric", "store personal", "share customer", "personal data",
    "identity", "pii", "sensitive", "confidential customer", "customer history",
    "transaction history", "without consent", "without explicit consent",
]

# LLM refusal / uncertainty patterns that indicate HIGH hallucination risk.
# These fire when the model declines to answer or admits it cannot verify.
_REFUSAL_PHRASES = [
    "i cannot", "i can't", "i will not", "i won't",
    "cannot provide", "cannot generate", "cannot create", "cannot produce",
    "i am unable", "i'm unable", "unable to provide", "unable to generate",
    "it would be inappropriate", "not appropriate to", "would not be appropriate",
    "i must decline", "i decline to", "this is not something i",
    "i should not", "i should not provide", "not able to provide",
    "this would violate", "this violates", "against policy",
]

# General uncertainty signals (non-refusal)
_UNCERTAINTY_PHRASES = [
    "i don't know", "i do not know", "unclear", "not specified",
    "cannot determine", "not sure", "uncertain", "no information",
    "not mentioned", "not available", "not stated", "not defined",
]

# Queries that are permission-seeking or generation-oriented stay MEDIUM risk
# even when the retrieved context is long — they involve interpretation, not
# plain policy lookup.
_AMBIGUOUS_QUERY_PATTERNS = [
    "is it permissible", "is it allowed", "is this allowed",
    "can fincorp", "can ai systems", "can we use", "are we allowed",
    "is this compliant", "is this okay", "would it be okay",
    "generate a list", "generate list", "list all", "enumerate all",
    " train ", "training data", "without consent",
]


# ---------------------------------------------------------------------------
# Toxicity scorer  (scored against the QUERY, not the LLM response,
# so that dangerous requests are always flagged even when the model refuses)
# ---------------------------------------------------------------------------

def score_toxicity(text: str) -> dict:
    """Return a keyword-derived toxicity float and safety boolean."""
    lower = text.lower()
    noise = random.uniform(-0.03, 0.03)

    if any(kw in lower for kw in _HIGH_TOXICITY_KEYWORDS):
        base = random.uniform(0.70, 0.95)
    elif any(kw in lower for kw in _MEDIUM_TOXICITY_KEYWORDS):
        base = random.uniform(0.20, 0.40)
    else:
        base = random.uniform(0.01, 0.08)

    toxicity = round(max(0.0, min(1.0, base + noise)), 4)
    return {"toxicity_score": toxicity, "is_safe": toxicity < TOXICITY_THRESHOLD}


# ---------------------------------------------------------------------------
# Hallucination scorer
# ---------------------------------------------------------------------------

def score_hallucination(query: str, response: str, context: str) -> dict:
    """
    Assess hallucination risk using three signals in priority order:
      1. Refusal or uncertainty language in the response  → HIGH
      2. Ambiguous / generation-oriented query nature     → MEDIUM (even with long context)
      3. Grounding context length                         → LOW / MEDIUM
    """
    response_lower = response.lower()
    query_lower = query.lower()

    # --- Priority 1: outright refusal or explicit uncertainty ---
    if (
        any(phrase in response_lower for phrase in _REFUSAL_PHRASES)
        or any(phrase in response_lower for phrase in _UNCERTAINTY_PHRASES)
    ):
        confidence = round(random.uniform(0.80, 0.92), 4)
        return {
            "hallucination_risk": "HIGH",
            "hallucination_confidence": confidence,
            "hallucination_label": "contradicts context",
        }

    ctx_len = len(context.strip()) if context else 0

    # --- Priority 2: permission-seeking or generation queries → MEDIUM ---
    if any(pat in query_lower for pat in _AMBIGUOUS_QUERY_PATTERNS):
        confidence = round(random.uniform(0.55, 0.72), 4)
        return {
            "hallucination_risk": "MEDIUM",
            "hallucination_confidence": confidence,
            "hallucination_label": "unverifiable claim",
        }

    # --- Priority 3: context-length grounding ---
    if ctx_len > 200:
        risk = "LOW"
        confidence = round(random.uniform(0.85, 0.95), 4)
        label = "consistent with context"
    elif ctx_len >= 50:
        risk = "MEDIUM"
        confidence = round(random.uniform(0.60, 0.75), 4)
        label = "unverifiable claim"
    else:
        risk = "MEDIUM"
        confidence = round(random.uniform(0.55, 0.65), 4)
        label = "unverifiable claim"

    return {
        "hallucination_risk": risk,
        "hallucination_confidence": confidence,
        "hallucination_label": label,
    }


# ---------------------------------------------------------------------------
# Bias / query category
# ---------------------------------------------------------------------------

_CATEGORY_RULES = [
    (["ssn", "social security", "password", "biometric", "pii", "personal data", "identity"], "customer data"),
    (["fraud", "threshold", "detection", "suspicious", "unauthorized", "stolen"], "fraud detection"),
    (["pci", "compliance", "penalty", "gdpr", "kyc", "aml", "policy", "regulation", "standard", "legal"], "compliance"),
    (["transaction", "chargeback", "disputed", "payment", "purchase", "transfer", "settlement", "merchant"], "transaction analysis"),
    (["model", " ml ", "machine learning", "ai system", "deploy", "credit scor", "algorithm", "training", "shadow"], "risk assessment"),
]


def score_bias_category(query: str) -> str:
    """Classify a query into a financial domain category."""
    lower = query.lower()
    for keywords, category in _CATEGORY_RULES:
        if any(kw in lower for kw in keywords):
            return category
    return "general financial"


# ---------------------------------------------------------------------------
# Risk aggregation
# ---------------------------------------------------------------------------

_HALLUCINATION_RISK_WEIGHTS = {"LOW": 0.05, "MEDIUM": 0.30, "HIGH": 0.80}


def compute_overall_risk(
    toxicity_score: float,
    hallucination_risk: str,
    hallucination_confidence: float,
) -> float:
    """Aggregate a 0–100 risk score. Toxicity 40%, hallucination 60%."""
    toxicity_component = min(toxicity_score, 1.0) * 100 * 0.40
    hall_base = _HALLUCINATION_RISK_WEIGHTS.get(hallucination_risk, 0.30)
    hall_component = (hall_base * hallucination_confidence) * 100 * 0.60
    return round(min(toxicity_component + hall_component, 100.0), 2)


# ---------------------------------------------------------------------------
# Unified scorer
# ---------------------------------------------------------------------------

def run_all_scorers(
    query: str,
    response: str,
    context: str,
    latency_seconds: float,
) -> dict:
    """Run all Responsible AI scorers and return a dict ready for log_query()."""
    # Toxicity is scored on the QUERY — dangerous requests must be flagged
    # even when the LLM correctly refuses them.
    tox = score_toxicity(query)
    hall = score_hallucination(query, response, context)
    category = score_bias_category(query)
    overall_risk = compute_overall_risk(
        tox["toxicity_score"],
        hall["hallucination_risk"],
        hall["hallucination_confidence"],
    )

    return {
        "query": query,
        "response": response,
        "context_used": context,
        "toxicity_score": tox["toxicity_score"],
        "is_safe": tox["is_safe"],
        "hallucination_risk": hall["hallucination_risk"],
        "hallucination_confidence": hall["hallucination_confidence"],
        "query_category": category,
        "latency_ms": round(latency_seconds * 1000, 2),
        "overall_risk_score": overall_risk,
    }

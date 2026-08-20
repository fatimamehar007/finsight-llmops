"""Tools available to the FinSight agent.

Base Llama 3 (via Ollama) has no native function-calling support (verified:
Ollama returns HTTP 400 "does not support tools" for llama3:latest), so these
are plain LangChain `Tool` objects invoked through a hand-rolled ReAct loop
(see backend/agent.py) rather than via `.bind_tools()`.
"""

import ast
import json
import operator
import re
from pathlib import Path

from langchain_core.tools import Tool

from backend import rag_engine

_TRANSACTIONS_PATH = Path(__file__).parent.parent / "data" / "transactions.json"

_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Mod: operator.mod,
}


def _load_transactions() -> list[dict]:
    with open(_TRANSACTIONS_PATH) as f:
        return json.load(f)


def _safe_eval(node) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError("only numeric constants are allowed")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"unsupported expression: {ast.dump(node)}")


def _calculator(expression: str) -> str:
    """Evaluate a numeric arithmetic expression. Input: a plain math expression, e.g. '12500 / 10000 * 100 - 100'."""
    try:
        cleaned = expression.strip().strip('"').strip("'")
        tree = ast.parse(cleaned, mode="eval")
        result = _safe_eval(tree.body)
        return f"{result:g}"
    except Exception as exc:
        return f"Error: could not evaluate '{expression}' ({exc})"


def _transaction_lookup(query: str) -> str:
    """Look up transaction record(s). Input: a transaction ID (e.g. 'TXN1005') or a filter phrase (e.g. 'flagged transactions over 10000')."""
    transactions = _load_transactions()
    query = query.strip().strip('"').strip("'")

    id_match = re.search(r"TXN\d+", query, re.IGNORECASE)
    if id_match:
        txn_id = id_match.group(0).upper()
        for t in transactions:
            if t["transaction_id"] == txn_id:
                return json.dumps(t)
        return f"No transaction found with ID {txn_id}."

    lower = query.lower()
    results = transactions
    if "flag" in lower:
        results = [t for t in results if t["fraud_flag"]]
    amount_match = re.search(r"(?:over|above|>)\s*\$?([\d,]+)", lower)
    if amount_match:
        threshold = float(amount_match.group(1).replace(",", ""))
        results = [t for t in results if t["amount"] > threshold]

    if not results:
        return "No transactions matched that filter."
    return json.dumps(results[:5])


def _policy_lookup(query: str) -> str:
    """Search the AI Governance & Compliance Policy document. Input: a natural-language question about policy, rules, or thresholds."""
    context = rag_engine.retrieve_context(query)
    return context if context.strip() else "No relevant policy text found for this query."


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="policy_lookup",
            description=_policy_lookup.__doc__,
            func=_policy_lookup,
        ),
        Tool(
            name="transaction_lookup",
            description=_transaction_lookup.__doc__,
            func=_transaction_lookup,
        ),
        Tool(
            name="calculator",
            description=_calculator.__doc__,
            func=_calculator,
        ),
    ]

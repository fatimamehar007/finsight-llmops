"""LangChain-based LLM runner using Ollama (llama3)."""

import os
import time

from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

_SYSTEM_PROMPT = (
    "You are a financial AI assistant for a regulated financial institution. "
    "Answer queries accurately using only the provided context. "
    "If unsure, say so explicitly. Do not hallucinate facts or invent figures. "
    "Keep responses concise and professional."
)


def _build_prompt(user_query: str, context: str) -> str:
    if context and context.strip():
        return (
            f"Context:\n{context}\n\n"
            f"Question: {user_query}\n\n"
            "Answer based strictly on the context above:"
        )
    return f"Question: {user_query}\n\nAnswer:"


def run_query(user_query: str, context: str = "") -> tuple[str, float]:
    """
    Run the user query through Ollama llama3 via LangChain.

    Returns:
        (response_text, latency_seconds)
    """
    try:
        from langchain_ollama import OllamaLLM
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_core.prompts import ChatPromptTemplate

        llm = OllamaLLM(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_HOST,
            temperature=0.1,
        )

        prompt = _build_prompt(user_query, context)
        full_prompt = f"{_SYSTEM_PROMPT}\n\n{prompt}"

        start = time.perf_counter()
        response = llm.invoke(full_prompt)
        latency = time.perf_counter() - start

        return str(response).strip(), latency

    except ImportError:
        # Fallback if langchain-ollama is not installed
        return _run_via_httpx(user_query, context)
    except Exception as exc:
        error_msg = str(exc)
        if "connection" in error_msg.lower() or "refused" in error_msg.lower():
            return (
                "Error: Cannot reach Ollama. Ensure Ollama is running with "
                f"`ollama serve` and the model '{OLLAMA_MODEL}' is pulled.",
                0.0,
            )
        return f"Error running LLM query: {error_msg}", 0.0


def _run_via_httpx(user_query: str, context: str) -> tuple[str, float]:
    """Fallback: call Ollama REST API directly via httpx."""
    import httpx

    prompt = _build_prompt(user_query, context)
    full_prompt = f"{_SYSTEM_PROMPT}\n\n{prompt}"

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": full_prompt,
        "stream": False,
    }

    try:
        start = time.perf_counter()
        resp = httpx.post(
            f"{OLLAMA_HOST}/api/generate",
            json=payload,
            timeout=120.0,
        )
        latency = time.perf_counter() - start
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip(), latency
    except httpx.ConnectError:
        return (
            "Error: Cannot reach Ollama. Ensure Ollama is running with "
            f"`ollama serve` and the model '{OLLAMA_MODEL}' is pulled.",
            0.0,
        )
    except Exception as exc:
        return f"Error calling Ollama API: {exc}", 0.0


def check_ollama_status() -> bool:
    """Return True if the Ollama server is reachable."""
    import httpx

    try:
        resp = httpx.get(f"{OLLAMA_HOST}/api/tags", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False

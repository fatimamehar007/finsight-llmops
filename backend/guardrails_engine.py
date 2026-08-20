"""NVIDIA NeMo Guardrails wrapper: input safety check + hallucination fact-check.

Rails are invoked directly through the action dispatcher instead of the full
Colang dialog manager (`rails.generate(...)`). The dialog manager also drives
intent classification and response generation through the same LLM, which
adds several more unreliable local-LLM calls for behavior FinSight doesn't
need — the agent (backend/agent.py) already produces the answer. Calling the
`self_check_input` / `self_check_facts` actions directly gives the same
NeMo Guardrails safety checks with a much smaller, more predictable surface.
"""

import asyncio
import os
import threading
from concurrent.futures import Future
from pathlib import Path

from dotenv import load_dotenv
from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.actions.actions import ActionResult

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

_CONFIG_DIR = Path(__file__).parent / "guardrails"

_rails: LLMRails | None = None

# LLMRails lazily creates an httpx.AsyncClient bound to whichever asyncio event
# loop is running the first time it's used. Calling it from a fresh
# `asyncio.run()` on every request (as a sync FastAPI route would) rebinds it
# to a new loop each time, so the client's connection pool is repeatedly torn
# down and rebuilt against a closed loop. Instead, one background thread runs
# a single persistent loop for the lifetime of the process, and every check is
# submitted onto it — the client is only ever touched from that one loop.
_loop = asyncio.new_event_loop()
_loop_thread = threading.Thread(target=_loop.run_forever, daemon=True)
_loop_thread.start()


def _run_coroutine(coro) -> object:
    future: Future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result()


def _get_rails() -> LLMRails:
    global _rails
    if _rails is None:
        config = RailsConfig.from_path(str(_CONFIG_DIR))
        config.models[0].model = OLLAMA_MODEL
        config.models[0].parameters["base_url"] = f"{OLLAMA_HOST}/v1"
        _rails = LLMRails(config)
    return _rails


async def _check_input_async(user_message: str) -> dict:
    rails = _get_rails()
    result, status = await rails.runtime.action_dispatcher.execute_action(
        "self_check_input",
        {
            "llm_task_manager": rails.runtime.llm_task_manager,
            "llm": rails.llm,
            "config": rails.config,
            "context": {"user_message": user_message},
        },
    )
    if status != "success":
        # Fail open: if the guardrails call itself errors (e.g. Ollama unreachable),
        # don't block legitimate traffic on an infra failure.
        return {"allowed": True, "error": f"self_check_input action status={status}"}
    # The action returns a plain bool when allowed, or an ActionResult(return_value=False, ...)
    # when it should be blocked — bool(ActionResult(...)) is always True (no __bool__ override),
    # so it must be unwrapped explicitly rather than coerced directly.
    allowed = result.return_value if isinstance(result, ActionResult) else bool(result)
    return {"allowed": bool(allowed)}


async def _check_facts_async(evidence: str, response: str) -> dict:
    if not evidence.strip():
        return {"grounded": True, "score": None, "reason": "no evidence to check against"}

    rails = _get_rails()
    result, status = await rails.runtime.action_dispatcher.execute_action(
        "self_check_facts",
        {
            "llm_task_manager": rails.runtime.llm_task_manager,
            "llm": rails.llm,
            "config": rails.config,
            "context": {"relevant_chunks": evidence, "bot_message": response},
        },
    )
    if status != "success":
        return {"grounded": True, "score": None, "error": f"self_check_facts action status={status}"}
    score = float(result)
    return {"grounded": score >= 0.5, "score": score}


def check_input(user_message: str) -> dict:
    return _run_coroutine(_check_input_async(user_message))


def check_facts(evidence: str, response: str) -> dict:
    return _run_coroutine(_check_facts_async(evidence, response))

"""Agentic query resolution: a hand-rolled ReAct loop over LangChain tools.

Why not `langchain.agents.create_agent` / `langgraph.prebuilt.create_react_agent`:
both require a chat model with native function-calling (`.bind_tools()`).
Ollama's `llama3:latest` returns HTTP 400 "does not support tools" for that
API, so the model is driven with classic text-based ReAct prompting instead —
it reasons in "Thought / Action / Action Input / Observation" turns and the
loop below parses and dispatches each action to the matching tool.

Each Observation is fed back as a genuine new chat turn (not concatenated
into one giant prompt) — Ollama's chat template makes the instruct model
treat a single mega-blob as one static instruction and reproduce the same
first move every time. Real conversation turns let it actually progress.
"""

import os
import re
import time

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from backend.tools import get_tools

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
MAX_ITERATIONS = 4

_TOOLS = {t.name: t for t in get_tools()}

_SYSTEM_PROMPT = """You are a financial compliance assistant for a regulated financial institution. Answer the question as best you can using only the tools below and the information they return — never invent policy text, transaction data, or numbers.

You have access to the following tools:

{tool_descriptions}

Use exactly this format:

Thought: reason about what to do next
Action: the action to take, must be one of [{tool_names}]
Action Input: the input to the action
(you will then be given an Observation with the result, and can continue with more Thought/Action/Action Input turns)

Once you have enough information and need no more tools, respond with EXACTLY this format and nothing else:
Thought: I now know the final answer
Final Answer: a concise, professional final answer to the original question

Never write "Action: None" — once ready, always go straight to "Final Answer:".

Example:
Question: Was transaction TXN1005 flagged for fraud, and what is its fraud score as a percentage?
Thought: I should look up TXN1005 first.
Action: transaction_lookup
Action Input: TXN1005
Observation: {{"transaction_id": "TXN1005", "fraud_flag": true, "fraud_score": 0.71, ...}}
Thought: The fraud score is 0.71, I should convert that to a percentage.
Action: calculator
Action Input: 0.71 * 100
Observation: 71
Thought: I now know the final answer
Final Answer: Yes, TXN1005 was flagged for fraud, with a fraud score of 71%.
"""

_ACTION_RE = re.compile(r"Action:\s*(.+?)\s*\nAction Input:\s*(.+?)\s*$", re.DOTALL)
_FINAL_RE = re.compile(r"Final Answer:\s*(.+)", re.DOTALL)


def _build_llm():
    from langchain_ollama import ChatOllama

    return ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_HOST, temperature=0.0)


def _parse_step(text: str):
    final_match = _FINAL_RE.search(text)
    if final_match:
        return "final", final_match.group(1).strip(), None

    action_match = _ACTION_RE.search(text)
    if action_match:
        tool_name = action_match.group(1).strip()
        tool_input = action_match.group(2).strip()
        return "action", tool_name, tool_input

    return "unparsed", text.strip(), None


def _run_tool(tools: dict, tool_name: str, tool_input: str) -> str:
    tool = tools.get(tool_name)
    if tool is None:
        return f"Error: unknown tool '{tool_name}'. Available tools: {', '.join(tools)}"
    try:
        return tool.func(tool_input)
    except Exception as exc:
        return f"Error running {tool_name}: {exc}"


def _force_final_answer(llm, messages: list) -> str:
    """Ask the model to wrap up, tolerating it re-echoing the Thought/Final Answer cue."""
    messages.append(HumanMessage("Thought: I now know the final answer\nFinal Answer:"))
    resp = llm.invoke(messages, stop=["\nObservation:"])
    kind, text, _ = _parse_step(resp.content)
    return text if kind == "final" else resp.content.strip()


def run_agent(query: str, use_rag: bool = True) -> dict:
    """Run the ReAct loop. Returns response, per-step tool trace, and RAG evidence for fact-checking.

    use_rag=False removes the policy_lookup tool entirely, so the agent can
    only use transaction_lookup / calculator — mirroring the old "ground in
    policy context (RAG)" toggle from the pre-agentic pipeline.
    """
    tools = {name: t for name, t in _TOOLS.items() if use_rag or name != "policy_lookup"}
    tool_descriptions = "\n".join(f"{t.name}: {t.description}" for t in tools.values())
    tool_names = ", ".join(tools)

    llm = _build_llm()
    system_prompt = _SYSTEM_PROMPT.format(
        tool_descriptions=tool_descriptions,
        tool_names=tool_names,
    )
    messages = [
        SystemMessage(system_prompt),
        HumanMessage(f"Question: {query}\nThought:"),
    ]

    trace: list[dict] = []
    evidence_chunks: list[str] = []
    start = time.perf_counter()

    def _finish(response_text: str) -> dict:
        return {
            "response": response_text,
            "trace": trace,
            "evidence": "\n\n---\n\n".join(evidence_chunks),
            "latency_seconds": time.perf_counter() - start,
        }

    for _ in range(MAX_ITERATIONS):
        resp = llm.invoke(messages, stop=["\nObservation:"])
        content = resp.content
        kind, a, b = _parse_step(content)

        if kind == "final":
            return _finish(a)

        if kind == "action" and a in tools:
            tool_name, tool_input = a, b
            observation = _run_tool(tools, tool_name, tool_input)
            if tool_name == "policy_lookup" and "No relevant policy" not in observation:
                evidence_chunks.append(observation)
            trace.append({"tool": tool_name, "input": tool_input, "output": observation})

            messages.append(AIMessage(content))
            messages.append(HumanMessage(f"Observation: {observation}\nThought:"))
            continue

        # Unrecognized action (e.g. "Action: None needed") or unparsed output —
        # nudge the model straight to a final answer instead of looping on it.
        messages.append(AIMessage(content))
        return _finish(_force_final_answer(llm, messages))

    # Ran out of iterations — force a summary from whatever evidence was gathered.
    return _finish(_force_final_answer(llm, messages))

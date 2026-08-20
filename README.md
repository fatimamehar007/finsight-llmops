# FinSight LLMOps

**Real-time Responsible AI observability and compliance monitoring for financial LLMs.**

Built to demonstrate production-grade LLMOps, RAG, hallucination mitigation, and AI governance engineering practices — covering every key requirement of a senior AI Engineer role in financial services.

---

## Architecture

FinSight is split into two independently deployable services. The Streamlit
frontend is a pure HTTP client — it never imports `backend/*` directly and
never talks to Ollama, ChromaDB, or the SQLite audit DB itself. Every piece
of business logic sits behind the REST API.

```
┌──────────────────────┐   HTTP/JSON   ┌───────────────────────────────────────────────────────────────┐
│  ui (Streamlit)       │──────────────▶│  api (FastAPI + Uvicorn)                                       │
│  Overview · Inspector │  POST /query  │                                                                 │
│  Analytics · Reports  │  POST /ingest │  1. NeMo Guardrails — self_check_input   (blocks jailbreaks)   │
└──────────────────────┘  GET  /health  │           │                                                     │
                                        │           ▼                                                     │
                                        │  2. Agent (ReAct loop, backend/agent.py)                        │
                                        │     decides which tool(s) to call, autonomously, per query:     │
                                        │       policy_lookup ──▶ ChromaDB (governance policy RAG)        │
                                        │       transaction_lookup ──▶ synthetic transaction records      │
                                        │       calculator ──▶ safe arithmetic (thresholds, %s)            │
                                        │           │                                                     │
                                        │           ▼                                                     │
                                        │  3. NeMo Guardrails — self_check_facts                          │
                                        │     (fact-checks the answer against retrieved policy evidence,  │
                                        │      withholds it if ungrounded — hallucination mitigation)      │
                                        │           │                                                     │
                                        │           ▼                                                     │
                                        │  4. Responsible AI scorers — toxicity · risk · category         │
                                        │           │                                                     │
                                        │           ▼                                                     │
                                        │  SQLite audit log  ·  fpdf2 compliance PDF  ·  CSV export        │
                                        └───────────────────────────────────────────────────────────────┘
                                                    │ (LLM calls: agent reasoning + both guardrail checks)
                                                    ▼
                                             Ollama — Llama 3
```

Both services build from the same image (same `requirements.txt`); Docker
Compose runs them as separate containers with `command:` overrides — see
[Docker Setup](#docker-setup).

### Why a hand-rolled ReAct loop instead of `langchain.agents.create_agent`

LangChain's modern agent constructors (`langchain.agents.create_agent`,
`langgraph.prebuilt.create_react_agent`) require a chat model with native
function-calling (`.bind_tools()`). Ollama's `llama3:latest` (base Llama 3,
not fine-tuned for tool use) returns an HTTP 400 **"does not support tools"**
for that API — confirmed by testing it directly. `backend/agent.py` instead
drives the model with classic text-based ReAct prompting: it reasons in
`Thought → Action → Action Input → Observation` turns, and each Observation
is fed back as a genuine new chat message (not concatenated into one giant
prompt) — Ollama's chat template makes an instruct model treat a single
mega-blob as one static instruction and reproduce the same first move every
time, so real conversation turns are what let it actually progress step to
step. It's still built on LangChain primitives (`langchain_core.tools`,
`langchain_ollama.ChatOllama`) — just without the tool-calling-only
high-level orchestrator.

### Why NeMo Guardrails is called directly rather than via `rails.generate()`

`backend/guardrails_engine.py` invokes the `self_check_input` and
`self_check_facts` actions directly through NeMo's action dispatcher, rather
than routing everything through the full Colang dialog manager. The dialog
manager also drives its own intent classification and response generation
through the same LLM — several more local-LLM calls for behavior this app
doesn't need, since the agent already produces the answer. Calling the two
safety actions directly gives the same real NeMo Guardrails checks (backed
by `backend/guardrails/config.yml` + `prompts.yml`, running against the same
local Llama 3 via Ollama's OpenAI-compatible `/v1` endpoint) with a much
smaller, more predictable surface.

---

## Features

- **REST API** — FastAPI service (`backend/api.py`) exposes `/query`, `/ingest`, `/rag/status`, `/logs`, `/stats`, `/reports/compliance`, `/health`; the Streamlit UI is one of potentially many clients — interactive docs at `/docs`
- **Agentic RAG** — a ReAct agent (`backend/agent.py`) autonomously decides, per query, whether to search the governance policy (RAG), look up a transaction record, run a calculation, or some combination — not a fixed retrieve-then-generate pipeline. Every tool call is logged and shown in the Inspector's "Agent tool trace"
- **NVIDIA NeMo Guardrails** — real `nemoguardrails` integration (`backend/guardrails_engine.py`, config in `backend/guardrails/`): an input rail (`self_check_input`) blocks jailbreak/policy-violating queries before the agent ever runs, and an output rail (`self_check_facts`) fact-checks the agent's answer against the policy text it retrieved, withholding it if ungrounded
- **LLMOps Pipeline** — End-to-end query tracking with latency, risk scoring, and a persistent audit log
- **RAG** — ChromaDB vector store with HuggingFace MiniLM-L6-v2 embeddings, grounding responses in a governance policy document
- **Hallucination Detection** — NeMo Guardrails fact-check (above) when policy evidence was retrieved; a context-grounding/refusal-pattern heuristic scorer as a fallback and for the dashboard's continuous LOW/MEDIUM/HIGH metric
- **Toxicity Scoring** — Keyword-based scorer flags sensitive or dangerous queries; unsafe requests trigger immediate alerts
- **Bias & Query Categorization** — Automatic financial domain classification (fraud detection, compliance, transaction analysis, customer data, risk assessment)
- **Risk Aggregation** — Weighted 0–100 overall risk score (toxicity 40%, hallucination 60%) displayed as a live Plotly gauge
- **AI Safety Assessment** — Dynamically generated plain-English assessment for every response, with risk-colored styling
- **Overview Dashboard** — System status banner, live KPI cards, risk trend chart, recent activity feed
- **Risk Analytics** — Time-series trends, scatter plots, pie/bar distributions, CSV export
- **Compliance Reports** — PDF audit reports with executive summary, risk tables, and rule-based recommendations; live compliance status (PASS / REVIEW REQUIRED / FAIL) shown before generation
- **Azure Deployment** — Docker + Azure Container Apps, two-service deploy script (see [Azure Deployment](#azure-deployment) for the Ollama-reachability caveat before running it)

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| REST API | FastAPI + Uvicorn (multi-worker) |
| LLM | Llama 3 via Ollama |
| Agent | Hand-rolled ReAct loop over LangChain tools (`langchain_core.tools`, `langchain_ollama.ChatOllama`) — see [why not create_agent](#why-a-hand-rolled-react-loop-instead-of-langchainagentscreate_agent) |
| Safety Guardrails | NVIDIA NeMo Guardrails (`nemoguardrails`) — input self-check + output fact-check rails |
| Orchestration | LangChain + langchain-ollama |
| Vector Database | ChromaDB (persistent) |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 |
| Toxicity Scorer | Keyword-based (configurable thresholds) |
| Hallucination Scorer | NeMo Guardrails fact-check + context-grounding/refusal-detection fallback |
| Frontend | Streamlit (4 pages, custom theme) — pure API client |
| Database | SQLite via SQLAlchemy |
| Charts | Plotly |
| PDF Reports | fpdf2, generated by the API service |
| Containerization | Docker + docker-compose (separate `api` / `ui` services) |
| Cloud | Azure Container Apps |

---

## Local Setup

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai) installed (`curl -fsSL https://ollama.com/install.sh | sh`)
- NVIDIA GPU (optional — improves inference speed)

### Step 1 — Clone & create environment

```bash
git clone <your-repo-url>
cd finsight-llmops
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Step 2 — Start Ollama and pull the model

```bash
# Ollama runs as a systemd service after install — no manual start needed
# Just pull the model (one-time, ~4.7 GB):
ollama pull llama3
```

### Step 3 — Generate the policy document and seed demo data

```bash
# Generate a synthetic AI Governance Policy PDF
python data/generate_policy.py

# Seed 10 demo queries (works even without Ollama via synthetic fallback)
python data/seed_queries.py
```

### Step 4 — Launch the API, then the frontend

The API is the only process that talks to Ollama, ChromaDB, and SQLite — start it first:

```bash
# Terminal 1 — REST API
uvicorn backend.api:app --reload --port 8000
# Interactive docs at http://localhost:8000/docs

# Terminal 2 — Streamlit frontend (pure API client)
streamlit run app/main.py
# Open http://localhost:8501
```

On first launch, click **"Load Policy"** in the Live Query Inspector sidebar to ingest the policy document via `POST /ingest`.

---

## Docker Setup

```bash
docker-compose up --build
# API available at   http://localhost:8000  (docs at /docs)
# UI  available at   http://localhost:8501
# Ollama must be running on the host machine
```

`docker-compose.yml` builds one image and runs it as two services — `api` (`uvicorn backend.api:app --workers 2`) and `ui` (`streamlit run app/main.py`, pointed at the `api` service via `API_BASE_URL=http://api:8000`). The `ui` container waits for the `api` container's healthcheck before starting. Volumes for `./chroma_db` and `./finsight.db` are mounted on the `api` service only, so data persists between restarts.

---

## Azure Deployment

```bash
chmod +x deploy_azure.sh
./deploy_azure.sh
```

The script logs into Azure, creates a resource group + Container Registry,
then deploys **three** Container Apps into one environment:

| App | Image | Ingress | Role |
|---|---|---|---|
| `finsight-ollama` | `ollama/ollama` | internal only | Serves Llama 3 |
| `finsight-api` | shared image, `uvicorn backend.api:app --workers 2` | external | Agent, guardrails, RAG, DB, PDF reports |
| `finsight-ui` | shared image, `streamlit run app/main.py` | external | Frontend — `API_BASE_URL` wired automatically to the deployed API's URL |

`finsight-api` reaches Ollama over the Container Apps environment's internal
DNS (`http://finsight-ollama`) — nothing needs a public Ollama endpoint.
An Azure Files share is mounted into the Ollama container's `/root/.ollama`
(toggle via `PERSIST_OLLAMA_MODELS` in the script) so the ~4.7GB model
persists across restarts instead of re-downloading every time.

**Before running it for real:**

1. **CPU-only inference.** Azure Container Apps only runs Llama 3 on CPU here
   — GPU workload profiles are a separate, pricier environment type this
   script doesn't set up. Expect each query (2-4+ sequential LLM calls: agent
   reasoning + 2 guardrail checks) to take low minutes rather than the
   ~10-30s seen in local testing against a GPU/Apple-silicon Ollama.
2. **Tooling.** The script needs the `az` CLI (authenticated via `az login`,
   which is interactive) and a running `docker` daemon on whatever machine
   runs it — it isn't something that can be run unattended or from a sandbox
   without both installed.
3. **Cost.** This creates real, billed Azure resources (Container Apps,
   Container Registry, Storage Account) that keep running — and billing —
   until torn down with `az group delete --name finsight-rg`.

Everything short of the actual `az`/`docker` execution — the FastAPI service,
the Dockerfile, `docker-compose.yml`, and this script — has been built and
tested locally (see the architecture section above); running it against a
real Azure subscription is the one step that has to happen on the user's own
machine.

---

## Screenshots

| Page | What you see |
|------|-------------|
| **Overview** | System status banner, colored KPI cards, hallucination distribution chart, risk trend line, recent activity feed |
| **Live Query Inspector** | Example query chips, full-width query form, st.metric badges, Plotly gauge with zone labels, AI Safety Assessment panel |
| **Risk Analytics** | 7 Plotly charts — trends, distributions, scatter — with captions explaining what to look for |
| **Compliance Reports** | Live compliance status (PASS/REVIEW REQUIRED/FAIL), one-click PDF generation with executive summary and recommendations |

---

## Project Motivation

> Built to demonstrate Responsible AI engineering practices including LLMOps, RAG, hallucination mitigation, and AI governance — covering the requirements of a senior AI Engineer role in financial services.

This project demonstrates:
- **Agentic system design**: a multi-service REST architecture (FastAPI + Streamlit) with a ReAct agent that autonomously selects tools to resolve financial queries
- **AI safety guardrails**: real NVIDIA NeMo Guardrails input/output rails mitigating jailbreaks and hallucinations
- **LLMOps** tooling and observability (latency tracking, audit logging, dashboards)
- **RAG** with production-grade vector retrieval to ground LLM outputs in verified policy
- **Responsible AI** scoring: toxicity, bias categorization, overall risk aggregation
- **Explainability** through a visible agent tool trace, plain-English AI Safety Assessments, and PDF compliance reports
- **MLOps** practices: containerization, reproducible builds, Azure cloud deployment

---

## License

MIT — use freely for portfolio and educational purposes.

# IntelliDesk — Agentic AI Business Operations Assistant
A production-shaped reference application showing how **Agentic AI**, **RAG**,
**LangChain/LangGraph**, and **MCP (Model Context Protocol)** fit together in
one business system.

**Business use case:** a business-operations and HR copilot that answers policy
questions from company documents (RAG), pulls live data from CRM / orders /
inventory / ticketing systems (MCP), and autonomously chains those steps to
resolve real requests (agent) — e.g.:

> *"Priya Patel says her order hasn't shipped — check it and do whatever our
> policy says."*
>
> Agent: looks up Priya → fetches her orders → finds order #103 pending 5+ days
> → retrieves shipping policy → policy says escalate → opens a high-priority
> ticket → replies with the ticket number and next steps.

---

## 1. Architecture

```
                        ┌───────────────────────────┐
   POST /chat  ───────► │   FastAPI  (src/api)      │
                        └────────────┬──────────────┘
                                     ▼
                 ┌────────────────────────────────────────┐
                 │  LangGraph ReAct Agent  (src/agent)    │
                 │  LLM: OpenAI via langchain-openai   │
                 │                                        │
                 │   ┌─ Reason ─► Act ─► Observe ─┐       │
                 │   └──────────── loop ──────────┘       │
                 └───────┬───────────────────┬────────────┘
                         │                   │
              LangChain tool           MCP client (stdio)
                         │                   │
                         ▼                   ▼
              ┌──────────────────┐  ┌─────────────────────────┐
              │  RAG (src/rag)   │  │ MCP Server              │
              │  Chroma (dense)  │  │ (src/mcp_server)        │
              │  + BM25 (sparse) │  │ lookup_customer         │
              │  + RRF fusion    │  │ get_customer_orders     │
              │        ▲         │  │ create_support_ticket   │
              │   ingestion:     │  │ update_ticket_status    │
              │   load→split→    │  │ check_inventory         │
              │   embed→store    │  │ get_sales_summary       │
              └──────────────────┘  └───────────┬─────────────┘
                        ▲                       ▼
              data/knowledge_base/     storage/business.db
              (policies, manuals)      (CRM/orders/tickets/stock/employees/leave)
```

### Why each technology is here 

| Layer | Technology | Job |
|---|---|---|
| Agentic AI | LangGraph `create_react_agent` | The LLM *decides* which tools to call, in what order, and when it has enough to answer. Multi-step, self-correcting. |
| RAG | Chroma + BM25 + RRF | Grounds answers in *your* documents — no hallucinated policy. Hybrid search catches both semantic matches and exact SKUs/IDs. |
| LangChain | `langchain-openai`, tools, splitters | The glue: model interface, tool abstraction, document processing. |
| MCP | FastMCP server + `langchain-mcp-adapters` | Standardized, reusable, auditable bridge to operational systems. The same server also works with other MCP-compatible clients — write the integration once. |

### The agentic loop (what makes it "agentic")

A plain RAG chatbot is a fixed pipeline: retrieve → stuff → answer.
IntelliDesk instead runs a **ReAct loop**:

1. **Reason** — the OpenAI model reads the request plus tool descriptions and plans.
2. **Act** — emits a tool call (`search_knowledge_base`, `lookup_customer`, …).
3. **Observe** — the tool result is appended to the conversation state.
4. **Repeat** — until it can answer, or `max_agent_iterations` is hit.

Guardrails in this repo: iteration cap, low temperature, "answer only from
retrieved sources" system-prompt rule, restate-before-write rule, priority
whitelist validation inside the MCP tools themselves.

### RAG pipeline detail (src/rag)

- **Ingestion** (`ingest.py`): `DirectoryLoader` per file type →
  `RecursiveCharacterTextSplitter` (800 chars, 120 overlap, start-index kept
  for citations) → local `all-MiniLM-L6-v2` embeddings → persistent Chroma
  collection with deterministic IDs (re-ingestion upserts, no duplicates).
  Folder names become a `domain` metadata field (`support/`, `hr/`) used for
  filtered retrieval.
- **Retrieval** (`retriever.py`): dense similarity search with a relevance
  threshold **+** BM25 keyword search, merged by Reciprocal Rank Fusion.
  Results are formatted with `[Source N: file, p.X]` headers so the agent can
  cite them.

### MCP detail (src/mcp_server)

`business_tools_server.py` is a self-contained FastMCP server. The agent
spawns it as a subprocess and speaks JSON-RPC over **stdio**
(`MCP_SERVERS` config in `src/agent/agent.py`); switch one line to `sse` to
run it as a network service. `langchain-mcp-adapters` discovers the server's
tools at startup and converts them into LangChain tools automatically — the
agent code never hard-codes a single business integration. The server also
exposes an MCP **resource** (`business://policies/priorities`) as an example
of read-only reference data.

---

## 2. Project layout 

```
intellidesk/
├── requirements.txt
├── .env.example
├── data/knowledge_base/        # RAG source documents (md/txt/pdf)
│   ├── support/  refund_policy.md, shipping_policy.md
│   └── hr/       leave_policy.md
├── scripts/seed_database.py    # demo CRM, inventory, employees and leave data
└── src/
    ├── config.py               # all settings (pydantic-settings + .env)
    ├── rag/ingest.py           # load → split → embed → store 
    ├── rag/retriever.py        # hybrid retrieval + RRF + citation formatting
    ├── mcp_server/business_tools_server.py
    ├── agent/agent.py          # LangGraph ReAct agent wiring RAG + MCP
    └── api/main.py             # FastAPI: /chat, /ingest, /health
```

## 3. Setup & run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env            # add your OPENAI_API_KEY

python -m scripts.seed_database         # 1) demo business DB
python -m src.rag.ingest data/knowledge_base   # 2) index documents

# 3a) one-shot CLI demo
python -m src.agent.agent "Can Daniel Okafor still return his 4K monitor?"

# 3b) or run as a service
uvicorn src.api.main:app --port 8000
curl -X POST localhost:8000/chat -H 'content-type: application/json' \
  -d '{"message":"How much stock of ErgoMouse M3 do we have, and what is our refund window for gold customers?","thread_id":"u1"}'
```

## 4. Example prompts that exercise the full stack 

- "What's the parental leave policy?" → RAG only.
- "Show Ananya Rao's leave balance." → MCP employee lookup + leave balance.
- "Can Arjun Nair take five days of annual leave?" → HR policy + MCP employee balance.
- "Create annual leave for Arjun from 2026-08-10 to 2026-08-12." → RAG + MCP read + MCP write.
- "Show sales for the last 30 days." → MCP only.
- "Priya's order 103 is stuck — handle it per policy." → RAG + MCP reads + MCP write (ticket).
- "A gold customer wants to return an opened gift card, allowed?" → RAG with policy nuance.

## 5. Hardening for production

- Swap SQLite for your real CRM/ERP behind the same MCP tool signatures.
- Run the MCP server over SSE/HTTP behind auth; log every tool call (it's a
  single audit chokepoint by design).
- Add human-in-the-loop approval on write tools (LangGraph `interrupt`).
- Move checkpointing from `MemorySaver` to Postgres/Redis for multi-instance.
- Add evaluation: golden Q&A set against the RAG layer; tool-call traces are
  already returned by `/chat` for observability.

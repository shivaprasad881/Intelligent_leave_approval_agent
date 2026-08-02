"""API layer — FastAPI wrapper so the agent becomes a deployable service.

Endpoints:
  POST /chat     {"message": "...", "thread_id": "user-42"}  -> agent answer + tool trace
  POST /ingest   {"path": "data/knowledge_base"}             -> (re)index documents
  GET  /health

Run:  uvicorn src.api.main:app --reload --port 8000
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.agent.agent import build_agent, run_turn
from src.rag.ingest import ingest


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    thread_id: str = "default"     # one thread per user/session => isolated memory


class ChatResponse(BaseModel):
    answer: str
    tool_trace: list[dict]


class IngestRequest(BaseModel):
    path: str = "data/knowledge_base"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build the agent (and its MCP session) ONCE at startup, reuse per request.
    async with build_agent() as agent:
        app.state.agent = agent
        yield


app = FastAPI(title="IntelliDesk — Agentic Business Assistant", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        out = await run_turn(app.state.agent, req.message, thread_id=req.thread_id)
        answer = out["answer"]
        if isinstance(answer, list):
            # Normalize structured content blocks returned by some model wrappers.
            parts: list[str] = []
            for block in answer:
                if isinstance(block, str):
                    parts.append(block)
                elif isinstance(block, dict) and block.get("type") in {"text", "output_text"}:
                    parts.append(str(block.get("text", "")))
            answer = "".join(parts)
        return ChatResponse(answer=str(answer), tool_trace=out["tool_trace"])
    except Exception as exc:  # noqa: BLE001 — surface agent errors to the client
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/ingest")
async def ingest_docs(req: IngestRequest):
    try:
        ingest(req.path)
        return {"status": "indexed", "path": req.path}
    except SystemExit as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

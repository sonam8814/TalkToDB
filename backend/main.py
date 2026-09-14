"""
main.py  –  FastAPI entry point (Phase 2 — streaming + /tables route)
"""
from __future__ import annotations

import json
import os
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent        import run_agent, AgentResult
from chroma_index import get_all_table_info, reset_index, get_chroma_collection
from database     import execute_query, get_db

load_dotenv()

CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000"
).split(",")

app = FastAPI(
    title       = "DB-Oracle API",
    description = "AI-powered natural language SQL agent for HR data",
    version     = "2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins  = CORS_ORIGINS,
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    import asyncio
    print("[startup] Warming up ChromaDB (background)...")
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, get_chroma_collection)
    print("[startup] Server ready — ChromaDB warming up in background.")


# ── Models ────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question:   str
    use_react:  bool = False   # set True to use ReAct agent loop


class QueryResponse(BaseModel):
    question:        str
    relevant_tables: list[str]
    sql:             str
    rows:            list[dict]
    row_count:       int
    summary:         str
    logs:            list[str]
    duration_ms:     int
    error:           str | None = None


class HealthResponse(BaseModel):
    status:   str
    version:  str
    database: str
    chroma:   str
    model:    str


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health_check():
    try:
        execute_query("SELECT COUNT(*) AS n FROM employees")
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {exc}"

    try:
        col           = get_chroma_collection()
        chroma_status = f"ok ({col.count()} documents indexed)"
    except Exception as exc:
        chroma_status = f"error: {exc}"

    return HealthResponse(
        status   = "ok" if db_status == "ok" else "degraded",
        version  = "2.0.0",
        database = db_status,
        chroma   = chroma_status,
        model    = os.getenv("OLLAMA_MODEL", "llama3"),
    )


# ── Main query endpoint ───────────────────────────────────────────────────────

@app.post("/query", response_model=QueryResponse)
def query_endpoint(payload: QueryRequest):
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    result: AgentResult = run_agent(payload.question, use_react=payload.use_react)

    return QueryResponse(
        question        = result.question,
        relevant_tables = result.relevant_tables,
        sql             = result.sql,
        rows            = result.rows,
        row_count       = result.row_count,
        summary         = result.summary,
        logs            = result.logs,
        duration_ms     = result.duration_ms,
        error           = result.error,
    )


# ── Streaming query endpoint ──────────────────────────────────────────────────

@app.post("/query/stream")
async def query_stream(payload: QueryRequest):
    """
    Server-Sent Events stream. Emits JSON objects as the pipeline progresses:
      { "type": "log",     "data": "Step 1 › ..." }
      { "type": "sql",     "data": "SELECT ..." }
      { "type": "rows",    "data": [...] }
      { "type": "summary", "data": "..." }
      { "type": "done",    "data": { ...full result... } }
      { "type": "error",   "data": "..." }
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        def emit(type_: str, data) -> str:
            return f"data: {json.dumps({'type': type_, 'data': data})}\n\n"

        try:
            yield emit("log", "Received question. Starting pipeline...")
            result: AgentResult = run_agent(
                payload.question,
                use_react=payload.use_react,
            )

            for log_line in result.logs:
                yield emit("log", log_line)

            if result.error:
                yield emit("error", result.error)
                return

            yield emit("sql",     result.sql)
            yield emit("rows",    result.rows)
            yield emit("summary", result.summary)
            yield emit("done",    {
                "row_count":   result.row_count,
                "duration_ms": result.duration_ms,
                "tables":      result.relevant_tables,
            })

        except Exception as exc:
            yield emit("error", str(exc))

    return StreamingResponse(
        event_generator(),
        media_type = "text/event-stream",
        headers    = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Schema / table info ───────────────────────────────────────────────────────

@app.get("/tables")
def list_tables():
    """Return metadata about all indexed tables."""
    return {"tables": get_all_table_info()}


@app.get("/schema")
def get_schema():
    """Return live column info from SQLite PRAGMA."""
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            table_names = [row["name"] for row in cursor.fetchall()]

            schema = {}
            for name in table_names:
                if not all(c.isalnum() or c == "_" for c in name):
                    continue
                pragma = conn.execute(f"PRAGMA table_info([{name}])")
                cols   = [desc[0] for desc in pragma.description]
                schema[name] = [dict(zip(cols, row)) for row in pragma.fetchall()]

        return {"schema": schema}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/admin/reset-index")
def reset_chroma_index():
    """Wipe and re-seed the ChromaDB index (dev/admin use only)."""
    try:
        reset_index()
        return {"status": "ok", "message": "ChromaDB index reset and re-seeded."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
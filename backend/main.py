from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent    import run_agent, AgentResult
from database import execute_query, get_chroma_collection

app = FastAPI(
    title="DB-Oracle API",
    description="AI-powered natural language SQL agent for HR data",
    version="1.0.0",
)

# Allow the React dev server (Vite default: 5173) and production origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Warm up ChromaDB on startup ───────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    print("[startup] Warming up ChromaDB collection...")
    get_chroma_collection()
    print("[startup] Ready.")


# ── Request / Response models ─────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    question:        str
    relevant_tables: list[str]
    sql:             str
    rows:            list[dict]
    row_count:       int
    logs:            list[str]
    error:           str | None = None


class HealthResponse(BaseModel):
    status:   str
    database: str
    chroma:   str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Verify database and ChromaDB are reachable."""
    try:
        execute_query("SELECT 1")
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {exc}"

    try:
        col = get_chroma_collection()
        chroma_status = f"ok ({col.count()} documents)"
    except Exception as exc:
        chroma_status = f"error: {exc}"

    return HealthResponse(
        status   = "ok" if db_status == "ok" else "degraded",
        database = db_status,
        chroma   = chroma_status,
    )


@app.post("/query", response_model=QueryResponse)
def query_endpoint(payload: QueryRequest):
    """
    Main endpoint. Accepts a plain-English question,
    runs the 4-step agent pipeline, returns SQL + results.
    """
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    result: AgentResult = run_agent(payload.question)

    return QueryResponse(
        question        = result.question,
        relevant_tables = result.relevant_tables,
        sql             = result.sql,
        rows            = result.rows,
        row_count       = result.row_count,
        logs            = result.logs,
        error           = result.error,
    )


@app.get("/schema")
def get_schema():
    """Return table names and column info directly from SQLite."""
    try:
        tables = execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        schema = {}
        for t in tables:
            table_name = t["name"]
            columns = execute_query(f"PRAGMA table_info({table_name})")
            schema[table_name] = columns
        return {"schema": schema}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
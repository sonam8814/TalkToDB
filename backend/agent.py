from __future__ import annotations

import re
from dataclasses import dataclass, field

from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

from database import (
    execute_query,
    retrieve_relevant_tables,
    get_schemas_for_tables,
)

# ── LLM setup ─────────────────────────────────────────────────────────────────
# Model name can be overridden via env var OLLAMA_MODEL
import os
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OLLAMA_BASE  = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

llm = OllamaLLM(model=OLLAMA_MODEL, base_url=OLLAMA_BASE, temperature=0)

# ── Prompt template ───────────────────────────────────────────────────────────
SQL_PROMPT = PromptTemplate(
    input_variables=["schema", "question"],
    template="""You are an expert SQLite SQL generator for an HR database.

RULES (strictly enforced):
1. Output ONE valid SQLite SELECT statement — nothing else.
2. Never use DROP, DELETE, UPDATE, INSERT, ALTER, CREATE, TRUNCATE or any DDL/DML.
3. Use table aliases for clarity in JOINs.
4. Use ISO date comparisons (YYYY-MM-DD) for date columns.
5. Do NOT wrap the query in markdown fences or add explanatory text.

AVAILABLE SCHEMA:
{schema}

USER QUESTION: {question}

SQL QUERY:""",
)

sql_chain = LLMChain(llm=llm, prompt=SQL_PROMPT)

# ── Safety guard ──────────────────────────────────────────────────────────────
_FORBIDDEN = re.compile(
    r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|CREATE|REPLACE)\b",
    re.IGNORECASE,
)


def _validate_sql(sql: str) -> str:
    """Strip markdown fences, trim whitespace, reject forbidden keywords."""
    # Remove ```sql … ``` wrappers the LLM sometimes adds
    sql = re.sub(r"```(?:sql)?", "", sql, flags=re.IGNORECASE).strip().rstrip("```").strip()

    match = _FORBIDDEN.search(sql)
    if match:
        raise ValueError(
            f"Security violation: keyword '{match.group()}' is not permitted. "
            "Only SELECT statements are allowed."
        )
    if not sql.upper().lstrip().startswith("SELECT"):
        raise ValueError(
            "Agent returned a non-SELECT statement. Query rejected for safety."
        )
    return sql


# ── Public interface ──────────────────────────────────────────────────────────

@dataclass
class AgentResult:
    question:       str
    relevant_tables: list[str]
    sql:            str
    rows:           list[dict]
    row_count:      int
    error:          str | None = None
    logs:           list[str]  = field(default_factory=list)


def run_agent(question: str) -> AgentResult:
    """
    Full 4-step pipeline:
      1. Retrieve relevant tables from ChromaDB
      2. Build schema context
      3. Generate SQL via Ollama LLM
      4. Execute against SQLite (read-only)
    """
    logs: list[str] = []

    # Step 1 – Smart retrieval
    logs.append("Step 1: Querying ChromaDB for relevant tables...")
    relevant_tables = retrieve_relevant_tables(question, n_results=3)
    logs.append(f"         Relevant tables: {relevant_tables}")

    # Step 2 – Schema context
    logs.append("Step 2: Building schema context...")
    schema_context = get_schemas_for_tables(relevant_tables)

    # Step 3 – SQL generation
    logs.append(f"Step 3: Sending question to Ollama ({OLLAMA_MODEL})...")
    try:
        raw_sql = sql_chain.run(schema=schema_context, question=question)
        logs.append(f"         Raw LLM output: {raw_sql[:120]}...")
    except Exception as exc:
        return AgentResult(
            question=question,
            relevant_tables=relevant_tables,
            sql="",
            rows=[],
            row_count=0,
            error=f"LLM error: {exc}",
            logs=logs,
        )

    # Step 3b – Safety validation
    try:
        safe_sql = _validate_sql(raw_sql)
        logs.append(f"         Validated SQL: {safe_sql}")
    except ValueError as exc:
        return AgentResult(
            question=question,
            relevant_tables=relevant_tables,
            sql=raw_sql,
            rows=[],
            row_count=0,
            error=str(exc),
            logs=logs,
        )

    # Step 4 – Execute
    logs.append("Step 4: Executing query against SQLite (read-only)...")
    try:
        rows = execute_query(safe_sql)
        logs.append(f"         Returned {len(rows)} row(s).")
        return AgentResult(
            question=question,
            relevant_tables=relevant_tables,
            sql=safe_sql,
            rows=rows,
            row_count=len(rows),
            logs=logs,
        )
    except Exception as exc:
        logs.append(f"         Execution error: {exc}")
        return AgentResult(
            question=question,
            relevant_tables=relevant_tables,
            sql=safe_sql,
            rows=[],
            row_count=0,
            error=f"SQL execution error: {exc}",
            logs=logs,
        )
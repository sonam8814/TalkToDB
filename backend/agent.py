"""
agent.py  –  LangChain AgentExecutor powered by a local Ollama LLM.

Pipeline (per query):
  1. ChromaDB semantic retrieval  → relevant table names
  2. Schema context assembly      → DDL + sample rows
  3. Ollama SQL generation        → raw SQL string
  4. Safety validation            → rejects non-SELECT
  5. SQLite execution (read-only) → result rows
  6. Optional summarisation       → one-sentence plain-English summary
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from dotenv  import load_dotenv
from langchain_ollama        import OllamaLLM
from langchain_classic.agents  import AgentExecutor, create_react_agent
from langchain_core.prompts    import PromptTemplate

from chroma_index import retrieve_relevant_tables, get_schema_context
from database     import execute_query, validate_sql
from tools        import get_all_tools
from prompts      import SQL_GENERATION_PROMPT, SUMMARISE_PROMPT, INTENT_PROMPT

load_dotenv()

# ── Configuration ─────────────────────────────────────────────────────────────
OLLAMA_MODEL       = os.getenv("OLLAMA_MODEL",       "llama3")
OLLAMA_BASE        = os.getenv("OLLAMA_BASE_URL",    "http://localhost:11434")
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", "0"))
OLLAMA_TIMEOUT     = int(os.getenv("OLLAMA_TIMEOUT", "120"))
MAX_AGENT_STEPS    = 6

def _validate_sql(raw: str) -> str:
    """Strip markdown fences, then structurally validate via sqlparse."""
    sql = re.sub(r"```(?:sql)?", "", raw, flags=re.IGNORECASE)
    sql = sql.replace("```", "").strip().rstrip(";").strip() + ";"
    return validate_sql(sql)


# ── LLM initialisation ────────────────────────────────────────────────────────

def _build_llm() -> OllamaLLM:
    return OllamaLLM(
        model       = OLLAMA_MODEL,
        base_url    = OLLAMA_BASE,
        temperature = OLLAMA_TEMPERATURE,
        timeout     = OLLAMA_TIMEOUT,
    )


# ── ReAct agent (tool-using) ──────────────────────────────────────────────────

REACT_SYSTEM = """You are DB-Oracle, an AI assistant that answers HR database questions using SQL.

You have access to these tools: {tools}
Tool names: {tool_names}

WORKFLOW — follow these steps in order:
1. Call retrieve_schema with the user's question to get the relevant DDL.
2. Write a SELECT query based on the schema returned.
3. Call execute_sql with your query.
4. Return the results to the user as a clean JSON array.

SAFETY: Never generate DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, or CREATE statements.

Use this format exactly:

Question: the input question
Thought: your reasoning
Action: the tool to use (one of: {tool_names})
Action Input: the input to the tool
Observation: the tool result
... (repeat Thought/Action/Action Input/Observation as needed)
Thought: I now have the final answer
Final Answer: [JSON array of rows]

Begin!

Question: {input}
Thought: {agent_scratchpad}"""


def _build_react_agent(llm: OllamaLLM) -> AgentExecutor:
    tools   = get_all_tools()
    prompt  = PromptTemplate.from_template(REACT_SYSTEM)
    agent   = create_react_agent(llm=llm, tools=tools, prompt=prompt)
    return AgentExecutor(
        agent          = agent,
        tools          = tools,
        verbose        = True,
        max_iterations = MAX_AGENT_STEPS,
        handle_parsing_errors = True,
        return_intermediate_steps = True,
    )


# ── Direct SQL pipeline (faster, more predictable) ────────────────────────────

def _direct_pipeline(
    question: str,
    llm: OllamaLLM,
    logs: list[str],
) -> tuple[str, list[dict]]:
    """
    Bypass the ReAct loop for straightforward questions.
    Step 1: ChromaDB retrieval
    Step 2: LLM SQL generation
    Step 3: Validate + execute
    """
    # Step 1
    logs.append("Step 1 › ChromaDB semantic retrieval")
    tables = retrieve_relevant_tables(question, n_results=3)
    logs.append(f"         Relevant tables: {tables}")

    # Step 2
    logs.append(f"Step 2 › LLM SQL generation ({OLLAMA_MODEL})")
    schema_ctx = get_schema_context(tables)
    raw_sql    = SQL_GENERATION_PROMPT | llm
    sql_output = raw_sql.invoke({
        "schema":   schema_ctx,
        "question": question,
        "dialect":  "SQLite",
    })
    logs.append(f"         Raw output: {str(sql_output)[:120]}")

    # Step 3
    logs.append("Step 3 › Safety validation")
    safe_sql = _validate_sql(str(sql_output))
    logs.append(f"         Validated SQL: {safe_sql}")

    # Step 4
    logs.append("Step 4 › SQLite execution (read-only)")
    rows = execute_query(safe_sql)
    logs.append(f"         Returned {len(rows)} row(s)")

    return safe_sql, rows


# ── Summarisation ─────────────────────────────────────────────────────────────

def _summarise(
    question: str,
    sql:      str,
    rows:     list[dict],
    llm:      OllamaLLM,
) -> str:
    """Generate a one-sentence plain-English summary of the results."""
    sample = json.dumps(rows[:5], default=str)
    chain  = SUMMARISE_PROMPT | llm
    try:
        summary = chain.invoke({
            "question":   question,
            "sql":        sql,
            "row_count":  len(rows),
            "sample_rows": sample,
        })
        return str(summary).strip()
    except Exception:
        return f"{len(rows)} result(s) found."


# ── Public result type ────────────────────────────────────────────────────────

@dataclass
class AgentResult:
    question:        str
    relevant_tables: list[str]
    sql:             str
    rows:            list[dict]
    row_count:       int
    summary:         str        = ""
    error:           str | None = None
    logs:            list[str]  = field(default_factory=list)
    duration_ms:     int        = 0


# ── Entry point ───────────────────────────────────────────────────────────────

def run_agent(question: str, use_react: bool = False) -> AgentResult:
    """
    Run the full pipeline for a natural-language HR question.

    Args:
        question:   Plain-English question from the user.
        use_react:  If True, use the ReAct tool-calling agent loop.
                    If False (default), use the faster direct pipeline.
    """
    logs: list[str] = []
    t0 = time.monotonic()

    llm = _build_llm()
    logs.append(f"[init] Model: {OLLAMA_MODEL}  |  Mode: {'react' if use_react else 'direct'}")

    # ── Intent classification: skip DB pipeline for non-database questions ──
    try:
        intent_chain = INTENT_PROMPT | llm
        intent = str(intent_chain.invoke({"question": question})).strip().upper()
        logs.append(f"[intent] Classification: {intent}")
    except Exception:
        intent = "DB"  # default to DB on failure so we don't block real queries

    if "DB" not in intent:
        elapsed = int((time.monotonic() - t0) * 1000)
        return AgentResult(
            question=question, relevant_tables=[], sql="",
            rows=[], row_count=0,
            summary="I'm an HR database assistant. Please ask me a question about employees, departments, salaries, or performance reviews.",
            error=None, logs=logs, duration_ms=elapsed,
        )

    try:
        if use_react:
            executor = _build_react_agent(llm)
            result   = executor.invoke({"input": question})
            # Extract SQL from intermediate steps
            sql, rows = "", []
            for step in result.get("intermediate_steps", []):
                action, obs = step
                if action.tool == "execute_sql":
                    sql = action.tool_input.get("sql", "")
                    try:
                        rows = json.loads(obs)
                    except Exception:
                        rows = []
                logs.append(f"[react] Tool: {action.tool}")
        else:
            sql, rows = _direct_pipeline(question, llm, logs)

    except ValueError as exc:
        elapsed = int((time.monotonic() - t0) * 1000)
        return AgentResult(
            question=question, relevant_tables=[], sql="",
            rows=[], row_count=0, error=str(exc), logs=logs,
            duration_ms=elapsed,
        )
    except Exception as exc:
        elapsed = int((time.monotonic() - t0) * 1000)
        logs.append(f"[error] {exc}")
        return AgentResult(
            question=question, relevant_tables=[], sql="",
            rows=[], row_count=0,
            error=f"Agent error: {exc}",
            logs=logs, duration_ms=elapsed,
        )

    # Summarise
    logs.append("Step 5 › Generating plain-English summary")
    summary = _summarise(question, sql, rows, llm)

    elapsed = int((time.monotonic() - t0) * 1000)
    logs.append(f"[done] Total duration: {elapsed}ms")

    # Re-extract table names from SQL for the response metadata
    table_pattern = re.findall(r'\bFROM\s+(\w+)|\bJOIN\s+(\w+)', sql, re.IGNORECASE)
    relevant_tables = list({t for pair in table_pattern for t in pair if t})

    return AgentResult(
        question        = question,
        relevant_tables = relevant_tables or ["employees"],
        sql             = sql,
        rows            = rows,
        row_count       = len(rows),
        summary         = summary,
        error           = None,
        logs            = logs,
        duration_ms     = elapsed,
    )
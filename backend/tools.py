"""
tools.py  –  Custom LangChain tools the SQL agent can invoke.

Tools exposed to the AgentExecutor:
  1. retrieve_schema  – ChromaDB lookup → returns relevant DDL context
  2. execute_sql      – Runs a validated SELECT against SQLite
  3. list_tables      – Returns all available table names (grounding tool)
"""
from __future__ import annotations

import json
import os
from typing import Type

from langchain_classic.tools import BaseTool
from pydantic import BaseModel, Field

from chroma_index import retrieve_relevant_tables, get_schema_context, TABLE_CATALOGUE
from database    import execute_query

MAX_ROWS = int(os.getenv("MAX_QUERY_ROWS", 500))


# ── Tool 1: retrieve_schema ───────────────────────────────────────────────────

class RetrieveSchemaInput(BaseModel):
    question: str = Field(description="The user's natural language question")


class RetrieveSchemaTool(BaseTool):
    name:        str = "retrieve_schema"
    description: str = (
        "Use this tool FIRST for every question. "
        "Input: the user's question. "
        "Output: the DDL schema of the most relevant database tables. "
        "You MUST call this before generating any SQL."
    )
    args_schema: Type[BaseModel] = RetrieveSchemaInput

    def _run(self, question: str) -> str:
        tables  = retrieve_relevant_tables(question, n_results=3)
        context = get_schema_context(tables)
        return f"Relevant tables: {tables}\n\n{context}"

    async def _arun(self, question: str) -> str:
        return self._run(question)


# ── Tool 2: execute_sql ───────────────────────────────────────────────────────

class ExecuteSQLInput(BaseModel):
    sql: str = Field(description="A valid SQLite SELECT statement to execute")


class ExecuteSQLTool(BaseTool):
    name:        str = "execute_sql"
    description: str = (
        "Execute a SQLite SELECT query against the HR database. "
        "Input: a complete SELECT SQL statement (no markdown fences). "
        "Output: JSON array of result rows, or an error message. "
        "Only SELECT is permitted — any other statement will be rejected."
    )
    args_schema: Type[BaseModel] = ExecuteSQLInput

    def _run(self, sql: str) -> str:
        # Strip accidental markdown fences
        sql = sql.replace("```sql", "").replace("```", "").strip()

        try:
            rows = execute_query(sql)
        except ValueError as exc:
            return f"ERROR (blocked): {exc}"
        except Exception as exc:
            return f"ERROR (execution): {exc}"

        if len(rows) > MAX_ROWS:
            rows = rows[:MAX_ROWS]
            return json.dumps(rows) + f"\n[Truncated to {MAX_ROWS} rows]"

        return json.dumps(rows, default=str)

    async def _arun(self, sql: str) -> str:
        return self._run(sql)


# ── Tool 3: list_tables ───────────────────────────────────────────────────────

class ListTablesInput(BaseModel):
    pass  # No input needed


class ListTablesTool(BaseTool):
    name:        str = "list_tables"
    description: str = (
        "Returns the names of all available tables in the database. "
        "Use this when unsure which tables exist. No input required."
    )
    args_schema: Type[BaseModel] = ListTablesInput

    def _run(self, **kwargs) -> str:
        tables = list(TABLE_CATALOGUE.keys())
        return f"Available tables: {tables}"

    async def _arun(self, **kwargs) -> str:
        return self._run()


# ── Tool registry ─────────────────────────────────────────────────────────────

def get_all_tools() -> list[BaseTool]:
    return [
        RetrieveSchemaTool(),
        ExecuteSQLTool(),
        ListTablesTool(),
    ]
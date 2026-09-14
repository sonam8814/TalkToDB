from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Generator

import chromadb
import sqlparse
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from sqlparse import tokens as T
from sqlparse.sql import Identifier, IdentifierList

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(__file__)
DB_PATH    = os.path.join(BASE_DIR, "data", "hr.db")
CHROMA_DIR = os.path.join(BASE_DIR, "data", "chroma")

# ── SQLite ────────────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection.  URI mode enforces read-only access."""
    uri = f"file:{DB_PATH}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row          # rows behave like dicts
    return conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context-manager wrapper — always closes the connection."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def execute_query(sql: str) -> list[dict]:
    """
    Execute a SELECT query and return rows as a list of dicts.
    Uses sqlparse-based structural validation before execution.
    """
    sql = validate_sql(sql)

    with get_db() as conn:
        cursor = conn.execute(sql)
        columns = [desc[0] for desc in cursor.description]
        rows    = [dict(zip(columns, row)) for row in cursor.fetchall()]

    return rows


# ── ChromaDB schema index ─────────────────────────────────────────────────────

# Table descriptions used for semantic retrieval
TABLE_DESCRIPTIONS: dict[str, str] = {
    "employees": (
        "The employees table stores all staff records. "
        "Columns: id (primary key), name (full name), department_id (foreign key to departments), "
        "salary (annual salary in USD), hire_date (ISO date of joining), role (job title). "
        "Use this table for questions about people, salaries, roles, tenure, or headcount."
    ),
    "departments": (
        "The departments table stores organisational units. "
        "Columns: id (primary key), name (department name), manager_id (employee id of the manager), "
        "location (city). "
        "Use this table for questions about teams, locations, or management structure."
    ),
    "performance_reviews": (
        "The performance_reviews table stores periodic employee evaluations. "
        "Columns: id (primary key), employee_id (foreign key to employees), "
        "rating (score from 1.0 to 5.0), review_date (ISO date of the review). "
        "Use this table for questions about performance, ratings, or appraisals."
    ),
}

# Canonical DDL used to feed exact schema to the LLM
TABLE_SCHEMAS: dict[str, str] = {
    "employees": (
        "CREATE TABLE employees (\n"
        "    id            INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    name          TEXT    NOT NULL,\n"
        "    department_id INTEGER NOT NULL REFERENCES departments(id),\n"
        "    salary        REAL    NOT NULL,\n"
        "    hire_date     TEXT    NOT NULL,   -- ISO format: YYYY-MM-DD\n"
        "    role          TEXT    NOT NULL\n"
        ");"
    ),
    "departments": (
        "CREATE TABLE departments (\n"
        "    id          INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    name        TEXT    NOT NULL,\n"
        "    manager_id  INTEGER,              -- FK -> employees.id\n"
        "    location    TEXT    NOT NULL\n"
        ");"
    ),
    "performance_reviews": (
        "CREATE TABLE performance_reviews (\n"
        "    id           INTEGER PRIMARY KEY AUTOINCREMENT,\n"
        "    employee_id  INTEGER NOT NULL REFERENCES employees(id),\n"
        "    rating       REAL    NOT NULL CHECK(rating BETWEEN 1.0 AND 5.0),\n"
        "    review_date  TEXT    NOT NULL    -- ISO format: YYYY-MM-DD\n"
        ");"
    ),
}

# ── SQL validation (sqlparse-based) ──────────────────────────────────────────

ALLOWED_TABLES = frozenset(TABLE_SCHEMAS.keys())

_FORBIDDEN_KEYWORDS = frozenset({
    "ATTACH", "DETACH", "REINDEX", "VACUUM", "PRAGMA",
})


def _extract_table_names(stmt) -> set[str]:
    """Extract table names referenced in FROM / JOIN clauses."""
    tables: set[str] = set()
    _walk_tokens_for_tables(stmt, tables)
    return tables


def _walk_tokens_for_tables(token_group, tables: set[str]) -> None:
    expect_table = False
    for token in token_group.tokens:
        if token.is_whitespace:
            continue

        if token.ttype is T.Keyword:
            upper = token.normalized.upper()
            if upper == "FROM" or "JOIN" in upper:
                expect_table = True
                continue
            else:
                expect_table = False

        if expect_table:
            if isinstance(token, IdentifierList):
                for ident in token.get_identifiers():
                    if isinstance(ident, Identifier):
                        name = ident.get_real_name()
                        if name:
                            tables.add(name.lower())
                expect_table = False
            elif isinstance(token, Identifier):
                name = token.get_real_name()
                if name:
                    tables.add(name.lower())
                expect_table = False
            elif token.ttype is T.Name:
                tables.add(token.normalized.lower())
                expect_table = False
            else:
                expect_table = False

        if hasattr(token, "tokens") and not isinstance(token, Identifier):
            _walk_tokens_for_tables(token, tables)


def validate_sql(sql: str) -> str:
    """
    Parse *sql* with sqlparse and structurally verify it is a single, safe
    SELECT against the known schema.  Returns cleaned SQL or raises ValueError.
    """
    sql = sql.strip()
    if not sql:
        raise ValueError("Empty SQL statement.")

    try:
        parsed = sqlparse.parse(sql)
    except Exception as exc:
        raise ValueError(f"SQL parse error: {exc}")

    statements = [s for s in parsed if str(s).strip()]
    if len(statements) != 1:
        raise ValueError("Exactly one SQL statement is permitted.")

    stmt = statements[0]

    if stmt.get_type() != "SELECT":
        raise ValueError(
            f"Only SELECT statements are permitted "
            f"(got '{stmt.get_type() or 'UNKNOWN'}')."
        )

    for token in stmt.flatten():
        upper = token.normalized.upper()
        if token.ttype is T.DML and upper != "SELECT":
            raise ValueError(
                f"Forbidden operation '{upper}'. Only SELECT is permitted."
            )
        if token.ttype is T.DDL:
            raise ValueError(f"Forbidden DDL operation '{upper}'.")
        if token.ttype is T.Keyword and upper in _FORBIDDEN_KEYWORDS:
            raise ValueError(f"Forbidden keyword '{upper}'.")
        if token.ttype is T.Name and upper == "LOAD_EXTENSION":
            raise ValueError("Forbidden function 'load_extension'.")

    unknown = _extract_table_names(stmt) - ALLOWED_TABLES
    if unknown:
        raise ValueError(
            f"Unknown table(s): {', '.join(sorted(unknown))}. "
            f"Allowed: {', '.join(sorted(ALLOWED_TABLES))}."
        )

    return sql


def _build_chroma_collection() -> chromadb.Collection:
    """Create (or load) the ChromaDB collection that indexes table descriptions."""
    ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_or_create_collection(
        name="table_schemas",
        embedding_function=ef,
    )

    # Only seed if the collection is empty
    if collection.count() == 0:
        ids        = list(TABLE_DESCRIPTIONS.keys())
        documents  = list(TABLE_DESCRIPTIONS.values())
        metadatas  = [{"table_name": t} for t in ids]

        collection.add(ids=ids, documents=documents, metadatas=metadatas)
        print(f"[chroma] Indexed {len(ids)} table descriptions.")
    else:
        print(f"[chroma] Collection already contains {collection.count()} entries.")

    return collection


# Module-level singleton — initialised once on import
_chroma_collection: chromadb.Collection | None = None


def get_chroma_collection() -> chromadb.Collection:
    global _chroma_collection
    if _chroma_collection is None:
        _chroma_collection = _build_chroma_collection()
    return _chroma_collection


def retrieve_relevant_tables(query: str, n_results: int = 2) -> list[str]:
    """
    Use ChromaDB semantic search to find the most relevant tables for a query.
    Returns a list of table names (e.g. ['employees', 'departments']).
    """
    collection = get_chroma_collection()
    results    = collection.query(query_texts=[query], n_results=n_results)
    table_names = [meta["table_name"] for meta in results["metadatas"][0]]
    print(f"[chroma] Relevant tables for query: {table_names}")
    return table_names


def get_schemas_for_tables(table_names: list[str]) -> str:
    """Return the DDL string for the requested tables, joined by newlines."""
    return "\n\n".join(TABLE_SCHEMAS[t] for t in table_names if t in TABLE_SCHEMAS)
from __future__ import annotations

import json
import os
from typing import Optional

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from dotenv import load_dotenv

load_dotenv()

CHROMA_DIR        = os.getenv("CHROMA_DIR",        "./data/chroma")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "table_schemas")
EMBED_MODEL       = os.getenv("CHROMA_EMBED_MODEL", "all-MiniLM-L6-v2")

# ── Table catalogue ───────────────────────────────────────────────────────────
# Each entry has a human-readable description (used for embedding)
# and a DDL string (fed verbatim to the LLM as schema context).

TABLE_CATALOGUE: dict[str, dict[str, str]] = {
    "employees": {
        "description": (
            "The employees table stores every staff record in the company. "
            "Use it for questions about individuals, salaries, job roles, tenure, "
            "hiring dates, headcount, or any people-related data. "
            "Columns: id, name, department_id (FK → departments), salary (USD annual), "
            "hire_date (YYYY-MM-DD), role (job title string)."
        ),
        "ddl": (
            "CREATE TABLE employees (\n"
            "    id            INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "    name          TEXT    NOT NULL,\n"
            "    department_id INTEGER NOT NULL REFERENCES departments(id),\n"
            "    salary        REAL    NOT NULL,          -- annual USD\n"
            "    hire_date     TEXT    NOT NULL,          -- YYYY-MM-DD\n"
            "    role          TEXT    NOT NULL\n"
            ");"
        ),
        "sample": (
            "Sample rows:\n"
            "  (1, 'Alice Chen', 1, 142000.0, '2019-03-15', 'Senior Engineer')\n"
            "  (2, 'Bob Martinez', 2, 95000.0, '2021-07-22', 'HR Manager')"
        ),
    },
    "departments": {
        "description": (
            "The departments table stores organisational units (teams). "
            "Use it for questions about department names, office locations, "
            "management structure, or grouping employees by team. "
            "Columns: id, name (department name), manager_id (FK → employees), "
            "location (city string)."
        ),
        "ddl": (
            "CREATE TABLE departments (\n"
            "    id          INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "    name        TEXT    NOT NULL,\n"
            "    manager_id  INTEGER,                     -- FK → employees.id\n"
            "    location    TEXT    NOT NULL\n"
            ");"
        ),
        "sample": (
            "Sample rows:\n"
            "  (1, 'Engineering', 3, 'San Francisco')\n"
            "  (2, 'Human Resources', 6, 'Austin')"
        ),
    },
    "performance_reviews": {
        "description": (
            "The performance_reviews table stores periodic employee evaluations. "
            "Use it for questions about performance ratings, appraisals, top performers, "
            "or low performers. "
            "Columns: id, employee_id (FK → employees), rating (REAL 1.0–5.0), "
            "review_date (YYYY-MM-DD)."
        ),
        "ddl": (
            "CREATE TABLE performance_reviews (\n"
            "    id           INTEGER PRIMARY KEY AUTOINCREMENT,\n"
            "    employee_id  INTEGER NOT NULL REFERENCES employees(id),\n"
            "    rating       REAL    NOT NULL CHECK(rating BETWEEN 1.0 AND 5.0),\n"
            "    review_date  TEXT    NOT NULL             -- YYYY-MM-DD\n"
            ");"
        ),
        "sample": (
            "Sample rows:\n"
            "  (1, 1, 4.8, '2024-01-15')\n"
            "  (2, 2, 4.2, '2024-01-20')"
        ),
    },
}


# ── ChromaDB client ───────────────────────────────────────────────────────────

_collection: Optional[chromadb.Collection] = None


def _get_collection() -> chromadb.Collection:
    global _collection
    if _collection is not None:
        return _collection

    ef = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    col    = client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},   # cosine similarity
    )

    if col.count() == 0:
        _seed_collection(col)

    _collection = col
    return col


def _seed_collection(col: chromadb.Collection) -> None:
    """Embed and store table descriptions in ChromaDB."""
    ids, docs, metas = [], [], []

    for table_name, info in TABLE_CATALOGUE.items():
        # Combine description + sample for richer embeddings
        document = f"{info['description']}\n\n{info['sample']}"
        ids.append(table_name)
        docs.append(document)
        metas.append({"table_name": table_name, "has_sample": "true"})

    col.add(ids=ids, documents=docs, metadatas=metas)
    print(f"[chroma] Seeded {len(ids)} table embeddings into '{CHROMA_COLLECTION}'.")


def reset_index() -> None:
    """Wipe and re-seed the ChromaDB collection (useful during development)."""
    global _collection
    ef = SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    client.delete_collection(CHROMA_COLLECTION)
    _collection = None
    col = client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    _seed_collection(col)
    _collection = col
    print("[chroma] Index reset complete.")


# ── Public API ────────────────────────────────────────────────────────────────

def retrieve_relevant_tables(question: str, n_results: int = 3) -> list[str]:
    """
    Semantically retrieve the most relevant table names for a natural-language question.
    Returns a list of table names ordered by relevance (most relevant first).
    """
    col = _get_collection()
    # Cap n_results to collection size
    n = min(n_results, col.count())
    results = col.query(
        query_texts=[question],
        n_results=n,
        include=["metadatas", "distances"],
    )

    # Filter by distance threshold (cosine distance < 0.8 = reasonably relevant)
    DISTANCE_THRESHOLD = 0.8
    tables = []
    for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
        if dist < DISTANCE_THRESHOLD:
            tables.append(meta["table_name"])

    # Always include employees as it's central to nearly every query
    if "employees" not in tables:
        tables.append("employees")

    print(f"[chroma] '{question[:60]}...' → relevant tables: {tables}")
    return tables


def get_schema_context(table_names: list[str]) -> str:
    """
    Return a full schema context string (DDL + samples) for the given tables.
    This is passed directly to the LLM as grounding context.
    """
    parts = []
    for name in table_names:
        if name in TABLE_CATALOGUE:
            info = TABLE_CATALOGUE[name]
            parts.append(f"-- {name}\n{info['ddl']}\n{info['sample']}")
    return "\n\n".join(parts)


def get_all_table_info() -> list[dict]:
    """Return metadata about all tables for the /tables API endpoint."""
    return [
        {
            "table":       name,
            "description": info["description"].split(".")[0] + ".",  # first sentence
            "columns":     _parse_ddl_columns(info["ddl"]),
        }
        for name, info in TABLE_CATALOGUE.items()
    ]


def _parse_ddl_columns(ddl: str) -> list[str]:
    """Extract column names from a DDL string (simple line-by-line parse)."""
    columns = []
    for line in ddl.splitlines():
        line = line.strip()
        if line and not line.startswith(("CREATE", ")", "--")):
            col_name = line.split()[0]
            columns.append(col_name)
    return columns

def get_chroma_collection() -> chromadb.Collection:
    """Public accessor for the ChromaDB collection singleton."""
    return _get_collection()
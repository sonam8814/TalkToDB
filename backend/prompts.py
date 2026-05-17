from langchain.prompts import PromptTemplate

# ── Intent classification prompt ─────────────────────────────────────────────
INTENT_PROMPT = PromptTemplate(
    input_variables=["question"],
    template="""You are a classifier. Decide whether the following user message is a question about an HR database (employees, departments, salaries, performance reviews, hiring, etc.) or NOT.

Reply with EXACTLY one word: "DB" if it is a database/HR question, or "GENERAL" if it is not.

User message: "{question}"

Answer:""",
)

# ── SQL generation prompt ─────────────────────────────────────────────────────
SQL_GENERATION_PROMPT = PromptTemplate(
    input_variables=["schema", "question", "dialect"],
    template="""You are an expert {dialect} SQL engineer working with an HR database.

STRICT RULES — violating any rule makes the response invalid:
1. Output ONLY a single valid {dialect} SELECT statement. No markdown. No explanation.
2. NEVER use: DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, CREATE, REPLACE, ATTACH.
3. Always qualify ambiguous column names with their table alias.
4. Use ISO 8601 date strings (YYYY-MM-DD) for all date comparisons.
5. For salary, always use the employees table. For names, always use the employees table.
6. When joining employees ↔ departments, join on employees.department_id = departments.id.
7. When joining employees ↔ performance_reviews, join on performance_reviews.employee_id = employees.id.
8. End your output with a semicolon.

DATABASE SCHEMA:
{schema}

QUESTION: {question}

SQL (SELECT only, no markdown):""",
)


# ── Table relevance scoring prompt ────────────────────────────────────────────
TABLE_RELEVANCE_PROMPT = PromptTemplate(
    input_variables=["tables_json", "question"],
    template="""Given this question: "{question}"

And these database tables:
{tables_json}

Return ONLY a JSON array of the table names most relevant to answer the question.
Example: ["employees", "departments"]
Return only the JSON array, nothing else.""",
)


# ── Result summarisation prompt ───────────────────────────────────────────────
SUMMARISE_PROMPT = PromptTemplate(
    input_variables=["question", "sql", "row_count", "sample_rows"],
    template="""You ran this SQL query to answer: "{question}"

SQL: {sql}
Rows returned: {row_count}
Sample of results: {sample_rows}

Write a single concise sentence (max 25 words) summarising what the data shows.
Do not repeat the SQL. Do not use markdown.""",
)
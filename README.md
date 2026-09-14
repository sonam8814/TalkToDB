# Talk to DB


## Project Overview (Plain English)
This project builds a "Magic Robot Librarian" (an AI Agent) that allows non-technical users to ask questions about their company's HR data in plain English. The agent translates the English question into a specialized database code (SQL), finds the right "shelves" (tables) in the library, fetches the actual numbers, and presents them on a hacker-style terminal screen.

---

## 1. Tech Stack
* **Backend:** Python (FastAPI)
* **AI Orchestration:** LangChain (SQL Agent)
* **LLM (The Brain):** Ollama (Local - using Llama3 or Mistral)
* **Vector Database:** ChromaDB (To store table schemas and find relevant tables)
* **Primary Database:** SQLite (Pre-loaded with HR/Company dataset)
* **Frontend:** React (Vite) + Tailwind CSS
* **UI Theme:** Terminal Aesthetic (Black background, green text, monospaced fonts)
* **Deployment:** Docker Compose (Containerizing Backend, Frontend, and DB)

---

## 2. Core Logic (The 4-Step Pipeline)
1.  **Smart Retrieval:** Use ChromaDB to store descriptions of database tables. When a user asks a question, the agent first queries ChromaDB to identify only the relevant tables (prevents context window overflow).
2.  **SQL Generation:** Pass the question and the selected table schemas to the Ollama LLM to write a precise SQL query.
3.  **Real-Data Execution:** Execute the query against the SQLite HR database.
4.  **Instant Delivery:** Return the raw data to the React UI for immediate display.

---

## 3. Data Specification (HR Dataset)
The demo database should include at least the following tables:
* **Employees:** (id, name, department_id, salary, hire_date, role)
* **Departments:** (id, name, manager_id, location)
* **Performance_Reviews:** (id, employee_id, rating, review_date)

---

## 4. Safety & Security
* **Read-Only Guardrails:** The SQL Agent must be restricted to `SELECT` statements only. Any `DROP`, `DELETE`, `UPDATE`, or `INSERT` attempts must be intercepted and blocked.
* **Database User:** Ensure the connection string or logic prevents write access.

---

## 5. UI/UX Requirements (Terminal Aesthetic)
* **Background:** `#000000` (Pitch Black)
* **Text:** `#00FF00` (Classic Matrix Green) or `#00CC00`
* **Font:** Monospace (Courier New, Fira Code, or JetBrains Mono)
* **Features:**
    * Command-line style input box.
    * "Typing" effect for AI responses.
    * Table results formatted in ASCII-style or clean borders.
    * "System Logs" panel showing the SQL query generated behind the scenes.

---

## 6. Proposed Folder Structure
```text
/ai-sql-agent
├── /backend
│   ├── main.py            # FastAPI Entry point
│   ├── database.py        # SQLite & ChromaDB setup
│   ├── agent.py           # LangChain + Ollama logic
│   ├── requirements.txt
│   └── /data              # SQLite .db files
├── /frontend
│   ├── /src
│   │   ├── components/    # Terminal UI components
│   │   ├── App.jsx
│   │   └── index.css      # Tailwind & Global styles
│   ├── package.json
│   └── tailwind.config.js
├── docker-compose.yml
└── README.md

"""
chroma_index.py  –  ChromaDB schema indexing and semantic table retrieval.

Responsibilities:
  - Build and persist a vector index of table descriptions
  - Retrieve the most relevant tables for a natural-language question
  - Expose raw DDL schemas for the retrieved tables
"""
// Backend
cd ~/Desktop/ai-sql-agent
source .venv/bin/activate
cd backend
../.venv/bin/python3 -m uvicorn main:app --reload --port 8000

// Frontend
cd /Users/sonamjha/Desktop/ai-sql-agent/frontend

npm install
npm run dev
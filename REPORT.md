# Self-Correcting SQL Agent
## Project Report

---

## 1. Executive Summary

The Self-Correcting SQL Agent is a full-stack system that translates natural-language requests into safe MySQL operations. It does not send raw LLM output straight to the database. Instead, it uses a staged pipeline that plans, generates, validates, classifies, authorizes, executes, corrects, explains, and logs every action.

The current codebase is organized into a `backend/` package, a `frontend/` React app, generated CRUD APIs in `generated/apis/`, and supporting logs in `logs/`.

---

## 2. What the Project Solves

The project addresses the gap between:

- non-technical users who want to ask questions in plain English
- and databases that require exact SQL and schema knowledge

It also reduces risk by blocking unsafe operations unless they are explicitly allowed and confirmed.

---

## 3. Main Features

- Natural language to MySQL SQL generation
- Live schema introspection
- Query planning
- Pre-execution validation
- Role-based authorization
- Dry-run preview mode
- High-risk confirmation gating
- Automatic SQL correction on failure
- Plain-English result explanation
- Audit logging
- Optional API generation
- Optional CRUD API generation per table

---

## 4. Tech Stack

### Backend

| Technology | Purpose |
|-----------|---------|
| Python | Application runtime |
| FastAPI | HTTP API server |
| Uvicorn | ASGI server |
| mysql-connector-python | MySQL access |
| sqlparse | SQL parsing and validation |
| python-dotenv | Environment loading |
| requests | LLM provider calls |

### Frontend

| Technology | Purpose |
|-----------|---------|
| React | UI framework |
| Vite | Dev server |
| CSS | Styling |

### Database

- MySQL 8.x
- Schema discovery via `INFORMATION_SCHEMA`

### LLM Providers

- Ollama
- Groq
- OpenAI

---

## 5. Architecture

```text
User -> React frontend -> FastAPI backend -> controller pipeline
      -> schema retrieval
      -> planning
      -> SQL generation
      -> validation
      -> policy check
      -> database execution
      -> correction/explanation/audit
```

The controller is the central orchestration layer. It coordinates the other modules and keeps the runtime flow consistent.

---

## 6. Module Summary

| File | Responsibility |
|------|----------------|
| `backend/core/controller.py` | End-to-end request pipeline |
| `backend/llm/sql_generator.py` | Generates SQL from prompts |
| `backend/services/validator.py` | Safety and schema validation |
| `backend/core/operation_guard.py` | Risk classification |
| `backend/core/policy_guard.py` | Role-based access control |
| `backend/db/database.py` | MySQL connection and execution |
| `backend/db/schema_retriever.py` | Live schema lookup |
| `backend/llm/planner.py` | Request planning |
| `backend/llm/self_corrector.py` | Error-driven retries |
| `backend/llm/explainer.py` | Result explanation |
| `backend/services/api_generator.py` | Generated route creation |
| `backend/services/api_runner.py` | Generated API server |
| `backend/core/audit_logger.py` | JSONL audit log |
| `backend/db/backup_manager.py` | Preflight backup artifact |
| `backend/api/main.py` | FastAPI app exposed to the frontend |

---

## 7. Safety Model

The project uses layered safety controls:

1. SQL syntax and schema validation
2. DDL blocking by default
3. Multi-statement blocking by default
4. UPDATE and DELETE protection without `WHERE`
5. Role-based authorization
6. High-risk confirmation
7. Optional preflight backup for critical operations

This makes the project suitable for guarded internal use rather than raw direct execution.

`WHERE` protection applies to row-level `DELETE` and `UPDATE` statements. `DROP TABLE` is handled differently because it is DDL, so it is governed by the DDL policy and high-risk confirmation instead of a `WHERE` requirement.

Natural-language requests like `delete table customers` are interpreted as schema-drop intent rather than row-delete intent.

---

## 8. API Generation

The project supports two kinds of generated APIs:

- a route string returned from a successful SQL query
- a full CRUD router written into `generated/apis/`

Those generated routers can be loaded by:

```powershell
python -m uvicorn backend.services.api_runner:app --reload --port 8001
```

When `api_runner` starts, it scans `generated/apis/`, imports the saved routers, mounts them on a dedicated FastAPI app, and exposes them through `/`, `/docs`, `/routes`, and the generated endpoint paths such as `/customers/`.

To discover the exact endpoint of a generated route, the simplest options are:

- open `/docs` to browse and test the endpoints
- open `/routes` to list mounted paths in JSON form
- inspect the generated file and read decorators like `@router.get("/tables")`
- combine that path with the runner base URL, such as `GET http://127.0.0.1:8001/tables`

---

## 9. Setup and Run

### Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Before setup, it helps to verify the installed tooling:

```powershell
python --version
node --version
npm --version
mysql --version
ollama --version
```

If you are using the sample database, prepare MySQL first and import `Sample_db.sql` before starting the backend. The `mysql -u root -p ...` commands prompt for the password once per command because they are separate invocations.

The main runtime toggles are:

- `dry_run`: preview without execution
- `generate_api`: also generate reusable API code
- `confirm_high_risk`: permit risky operations when policy allows them

### Run backend

```powershell
python -m uvicorn backend.api.main:app --reload --port 8000
```

### Run frontend

```powershell
cd frontend
npm install
npm run dev
```

---

## 10. Sample Database

The included `Sample_db.sql` file creates a compact ecommerce-style schema. It is useful for:

- smoke testing the agent
- checking SQL generation quality
- validating the safety rules
- demonstrating CRUD generation

It also includes `newsletter_subscribers` and `campaign_drafts`, two independent domain-relevant tables that make destructive-operation testing easier without foreign-key conflicts.

## 11. Quality Benchmark

The repository also includes [`_quality_benchmark.py`](/c:/Users/Chandu/OneDrive/Desktop/sql-agent/_quality_benchmark.py). It is a local quality-check script that sends sample prompts to the running backend and verifies expected SQL patterns, risk levels, and correction counts.

Use it after the backend is running:

```powershell
python _quality_benchmark.py
```

---

## 12. Status

The current project is organized into clearer folders, uses a single supported backend entrypoint, and no longer includes the alternate single-file UI path. The intended workflow is now:

1. create a virtual environment
2. install dependencies
3. configure `.env`
4. start the backend
5. start the frontend

The repository documentation now uses SVG diagrams under `docs/diagrams/` so the explanations render cleanly on GitHub without depending on local screenshots.

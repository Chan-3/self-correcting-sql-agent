# Self-Correcting SQL Agent - Project Documentation

**Course:** Semester 6 - Large Language Models  
**Project Type:** Applied LLM Engineering

---

## 1. Project Overview

The Self-Correcting SQL Agent converts natural-language questions into validated MySQL queries. It inspects the live schema, generates SQL with an LLM or deterministic shortcuts, validates the query, checks policy and risk, executes it, and explains the result in plain English.

The project also supports optional API generation. A successful SQL query can be turned into a reusable FastAPI route, and table-level CRUD APIs can be generated into `generated/apis/`.

---

## 2. What the System Does

Typical flow:

1. User submits a plain-English request.
2. The backend reads the current MySQL schema.
3. A plan is built for the request.
4. SQL is generated.
5. The SQL is validated for schema and safety rules.
6. Risk and role checks decide whether execution is allowed.
7. The query is executed or previewed as a dry run.
8. If execution fails, the system tries to correct the SQL.
9. The result is explained in simple language.
10. Every action is logged for auditability.

---

## 3. Current Project Structure

```text
sql-agent/
├─ backend/
│  ├─ api/main.py
│  ├─ core/
│  │  ├─ config.py
│  │  ├─ controller.py
│  │  ├─ audit_logger.py
│  │  ├─ operation_guard.py
│  │  └─ policy_guard.py
│  ├─ db/
│  │  ├─ database.py
│  │  ├─ schema_retriever.py
│  │  └─ backup_manager.py
│  ├─ llm/
│  │  ├─ llm_client.py
│  │  ├─ planner.py
│  │  ├─ sql_generator.py
│  │  ├─ self_corrector.py
│  │  └─ explainer.py
│  └─ services/
│     ├─ validator.py
│     ├─ api_generator.py
│     └─ api_runner.py
├─ frontend/
├─ generated/apis/
├─ logs/
├─ Sample_db.sql
└─ requirements.txt
```

---

## 4. Technology Stack

### Backend

| Technology | Purpose |
|-----------|---------|
| Python | Core application language |
| FastAPI | HTTP API backend |
| Uvicorn | ASGI server |
| mysql-connector-python | MySQL driver |
| sqlparse | SQL parsing |
| python-dotenv | `.env` loading |
| requests | LLM HTTP calls |

### Frontend

| Technology | Purpose |
|-----------|---------|
| React | User interface |
| Vite | Development server and bundler |
| Vanilla CSS | Styling |

### LLM Providers

- Ollama for local inference
- Groq for cloud inference
- OpenAI for cloud inference

### Database

- MySQL with live schema introspection through `INFORMATION_SCHEMA`

---

## 5. Important Backend Modules

| Module | Responsibility |
|--------|----------------|
| `backend/core/controller.py` | Main orchestration pipeline |
| `backend/llm/sql_generator.py` | Natural language to SQL generation |
| `backend/services/validator.py` | SQL safety and schema validation |
| `backend/core/operation_guard.py` | Operation and risk classification |
| `backend/core/policy_guard.py` | Role-based authorization |
| `backend/db/database.py` | MySQL connection and execution helpers |
| `backend/db/schema_retriever.py` | Schema introspection |
| `backend/llm/self_corrector.py` | SQL correction loop |
| `backend/llm/explainer.py` | Plain-English result explanation |
| `backend/services/api_generator.py` | API route and CRUD generation |
| `backend/services/api_runner.py` | Mounts generated CRUD routes |
| `backend/core/audit_logger.py` | JSONL audit log |
| `backend/db/backup_manager.py` | Preflight backup helper |

---

## 6. Pipeline Flow

1. The user writes a request in English.
2. The controller fetches the current schema.
3. The planner builds a structured plan.
4. The SQL generator writes the first query.
5. The validator checks syntax, schema, and safety rules.
6. The policy guard checks role and risk permissions.
7. If dry run is off, the query is executed on MySQL.
8. If execution fails, the self-corrector retries with the error message.
9. If execution succeeds, the explainer summarizes the result.
10. The audit logger records the run.

---

## 7. Safety Design

The project enforces multiple safety layers:

- DDL is blocked by default
- Multi-statement SQL is blocked by default
- DELETE and UPDATE without `WHERE` are rejected
- High-risk operations need confirmation
- Role-based access control limits what each role can do
- Optional preflight backup is created before confirmed critical operations

The main request body supports:

- `dry_run`
- `generate_api`
- `confirm_high_risk`

### 7.1 Toggle behavior

The frontend and API expose three main execution controls:

- `dry_run=true`: validate and preview the SQL without running it.
- `dry_run=false`: execute the SQL after validation, risk checks, and authorization.
- `generate_api=true`: return generated FastAPI route code for successful queries, or generate CRUD routers when requested.
- `generate_api=false`: handle only the query pipeline.
- `confirm_high_risk=true`: allow high-risk or critical operations to proceed when the role and safety policy allow them.
- `confirm_high_risk=false`: block high-risk operations before execution.

### 7.2 Row deletes vs table drops

`WHERE` is required for row-level `DELETE` and `UPDATE` statements only.

- `DELETE ... WHERE ...` and `UPDATE ... WHERE ...` are valid guarded patterns.
- `DELETE` or `UPDATE` without `WHERE` are rejected by the validator.
- `DROP TABLE` does not use `WHERE` because it is a DDL operation, not a row delete.

To execute `DROP TABLE`, the request must pass the DDL policy, the current role must allow the operation, and the request must be confirmed as high-risk.

---

## 8. API Generation

There are two API-generation paths:

### 8.1 Generated Route from SQL

If `generate_api=true`, a successful query can also produce a FastAPI route string.

### 8.2 Generated CRUD API

If the user asks for CRUD generation, `backend/services/api_generator.py` writes a route file to `generated/apis/<table>.py`.

Those generated files are loaded by `backend/services/api_runner.py`.

Run the generated API server with:

```powershell
python -m uvicorn backend.services.api_runner:app --reload --port 8001
```

When `api_runner` starts, it scans `generated/apis/`, imports each Python file, mounts any exported `router`, and serves the resulting endpoints through FastAPI. The generated routes then become available through `/docs`, `/routes`, and the mounted API paths such as `/customers/`.

To identify the exact endpoint for a generated file:

- open `/docs` for the interactive Swagger UI
- open `/routes` for a plain JSON list of mounted paths
- inspect the generated file itself and read the route decorator such as `@router.get("/tables")`
- call that path on the runner host, for example `GET http://127.0.0.1:8001/tables`

---

## 9. Setup and Run

### Prerequisites

- Python 3.11 or 3.12
- Node.js LTS
- MySQL 8.x
- Ollama or a valid Groq/OpenAI key

### Check prerequisites

Before setup, confirm the required tools are installed:

```powershell
python --version
node --version
npm --version
mysql --version
ollama --version
```

If Ollama is installed but not running, start it with:

```powershell
ollama serve
```

### Database preparation

The app needs a real MySQL database before it starts. Use one of these two paths:

**Sample database path**

1. Start MySQL.
2. Create the database if needed.

```powershell
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS shop_db;"
```

3. Import the sample schema and seed data.

```powershell
Get-Content .\Sample_db.sql | mysql -u root -p shop_db
```

4. Set `DB_NAME=shop_db` in `.env`.

Each `mysql -u root -p ...` command will ask for the MySQL password because it is a separate invocation. If you prefer to enter the password once, start an interactive MySQL session with `mysql -u root -p` and run the SQL commands there.

**Custom database path**

1. Create your own database in MySQL.
2. Update `DB_NAME` in `.env`.
3. Confirm the tables exist before running the agent.

### Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

If your database is not ready yet, complete the database preparation step above before starting the backend.

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

The included `Sample_db.sql` file creates a small ecommerce schema that is useful for testing the agent. After importing it, the project can answer questions against tables such as `customers`, `orders`, `products`, and `reviews`.

It also includes independent ecommerce-adjacent tables, `newsletter_subscribers` and `campaign_drafts`, which are useful for safe delete, update, truncate, and drop testing without foreign-key conflicts.

---

## 11. Testing

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## 12. Quality Benchmark

The repository includes [`_quality_benchmark.py`](/c:/Users/Chandu/OneDrive/Desktop/sql-agent/_quality_benchmark.py), a lightweight local benchmark for backend quality checks.

It sends sample prompts to the running backend and records:

- whether the call succeeded
- whether the generated SQL matches an expected pattern
- whether the risk classification matches expectations
- how many correction attempts were needed

Run it after the backend has started:

```powershell
python _quality_benchmark.py
```

---

## 13. Documentation Summary

This version of the project is intentionally simplified:

- backend code is grouped by responsibility
- the alternate single-file UI entrypoint has been removed
- startup instructions are now focused on the portable path
- the main supported experience is FastAPI backend + React frontend
- GitHub-facing documentation diagrams live in `docs/diagrams/` as SVG assets referenced by `README.md`

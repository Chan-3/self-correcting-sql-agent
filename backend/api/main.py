"""
FastAPI backend for the React UI.
Run with: uvicorn backend.api.main:app --reload
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.core import config
from backend.core.audit_logger import read_recent_audit_events
from backend.core.controller import run_query
from backend.db.database import list_databases, set_active_database, test_connection
from backend.llm.llm_client import is_llm_available, get_provider_label
from backend.db.schema_retriever import get_schema
from backend.services.api_generator import (
    detect_crud_table,
    generate_crud_api,
    list_generated_apis,
    list_generated_api_files,
)


class QueryRequest(BaseModel):
    request: str = Field(min_length=1)
    generate_api: bool = False
    dry_run: bool = False
    confirm_high_risk: bool = False


class SelectDatabaseRequest(BaseModel):
    database_name: str = Field(min_length=1)


class GenerateCrudRequest(BaseModel):
    table_name: str = Field(min_length=1)


app = FastAPI(title="SQL Agent Web API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "database": test_connection(),
        "database_name": config.DB_NAME,
        "llm": is_llm_available(),
        "provider": get_provider_label(),
    }


@app.get("/api/databases")
def databases() -> dict:
    try:
        return {
            "databases": list_databases(),
            "active_database": config.DB_NAME,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database listing failed: {exc}") from exc


@app.post("/api/database/select")
def select_database(payload: SelectDatabaseRequest) -> dict:
    try:
        selected = set_active_database(payload.database_name)
        return {
            "success": True,
            "database_name": selected,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database switch failed: {exc}") from exc


@app.get("/api/schema")
def schema() -> dict:
    try:
        return {"schema": get_schema()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Schema retrieval failed: {exc}") from exc


@app.get("/api/examples")
def examples() -> dict:
    return {
        "examples": [
            "Show all tables and row counts",
            "Find duplicate email addresses",
            "List the 10 most recently created records",
            "Delete from reviews where id = 15",
            "Delete from newsletter_subscribers where id = 1",
            "Truncate table campaign_drafts",
            "Create CRUD API for customers",
        ]
    }


@app.get("/api/capabilities")
def capabilities() -> dict:
    return {
        "app_role": config.APP_ROLE,
        "supports": {
            "natural_language_sql": True,
            "api_generation": True,
            "self_correction": True,
            "dry_run": True,
            "high_risk_confirmation": True,
            "audit_logging": True,
            "database_switching": True,
            "preflight_backup": True,
        },
        "controls": {
            "dry_run": {
                "checked": "Preview SQL, validation, and execution plan without running MySQL statements.",
                "unchecked": "Run the SQL after validation, role checks, and risk checks pass.",
            },
            "generate_api": {
                "checked": "Also generate reusable FastAPI route code for successful requests.",
                "unchecked": "Only handle the query pipeline and return the query result.",
            },
            "confirm_high_risk": {
                "checked": "Allow high-risk or critical operations to continue when policy permits them.",
                "unchecked": "Block high-risk or critical operations before execution.",
            },
        },
        "destructive_operations": {
            "update_delete": "UPDATE and DELETE statements must include a WHERE clause.",
            "drop_table": "DROP TABLE does not use WHERE because it is DDL. Requests like `drop table ...` or `delete table ...` need DDL permission, admin-level policy, and explicit high-risk confirmation.",
        },
        "quality_tools": {
            "unit_tests": 'python -m unittest discover -s tests -p "test_*.py"',
            "benchmark": "python _quality_benchmark.py",
            "note": "Unit tests and the benchmark are recommended for validation, but they are not required to run the product.",
        },
        "generated_api_storage": {
            "single_route_generation": "Generated route files are saved under generated/apis/query_<timestamp>_<slug>.py.",
            "crud_generation": "CRUD files are saved under generated/apis/<table>.py.",
            "usage": "Start `python -m uvicorn backend.services.api_runner:app --reload --port 8001` to serve all saved generated routers.",
            "runner_behavior": "api_runner loads every generated router, exposes them through FastAPI, and serves docs at /docs plus route discovery at /routes.",
        },
    }


@app.get("/api/audit")
def audit(limit: int = 100) -> dict:
    safe_limit = max(1, min(limit, 1000))
    return {
        "events": read_recent_audit_events(limit=safe_limit),
        "count": safe_limit,
    }


@app.post("/api/query")
def query(payload: QueryRequest) -> dict:
    result = run_query(
        payload.request.strip(),
        generate_api=payload.generate_api,
        execute=not payload.dry_run,
        confirmed=payload.confirm_high_risk,
    )
    return {
        "success": result.success,
        "sql": result.sql,
        "rows": result.rows,
        "affected_rows": result.affected_rows,
        "error": result.error,
        "correction_attempts": result.correction_attempts,
        "validation_warnings": result.validation_warnings,
        "api_route": result.api_route,
        "duration_ms": result.duration_ms,
        "operation_type": result.operation_type,
        "risk_level": result.risk_level,
        "intent_risk_level": result.intent_risk_level,
        "requires_confirmation": result.requires_confirmation,
        "execution_plan": result.execution_plan,
        "dry_run": payload.dry_run,
        "backup_path": result.backup_path,
        "app_role": config.APP_ROLE,
        "plan": result.plan,
        "explanation": result.explanation,
        "generated_file": result.generated_file,
    }


@app.post("/api/generate-crud")
def generate_crud(payload: GenerateCrudRequest) -> dict:
    """
    Directly generate a full CRUD API file for a given table name.
    The file is written to generated/apis/<table>.py and auto-loaded
    by the api_runner on next start.
    """
    try:
        schema = get_schema()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Schema retrieval failed: {exc}") from exc

    table = payload.table_name.strip()
    if table not in schema:
        available = sorted(schema.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Table '{table}' not found. Available: {available}",
        )

    try:
        code, filepath = generate_crud_api(table, schema)
        return {
            "success": True,
            "table": table,
            "generated_file": filepath,
            "code": code,
            "endpoints": [
                f"GET    /{table}/",
                f"GET    /{table}/{{id}}",
                f"POST   /{table}/",
                f"PUT    /{table}/{{id}}",
                f"DELETE /{table}/{{id}}",
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CRUD generation failed: {exc}") from exc


@app.get("/api/generated-apis")
def generated_apis() -> dict:
    """List saved generated API files and their storage details."""
    tables = list_generated_apis()
    files = list_generated_api_files()
    return {
        "tables": tables,
        "files": files,
        "count": len(files),
        "storage_dir": "generated/apis",
        "runner_command": "python -m uvicorn backend.services.api_runner:app --reload --port 8001",
        "note": "Restart api_runner to load newly generated files.",
    }

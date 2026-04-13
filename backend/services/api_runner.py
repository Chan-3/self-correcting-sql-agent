"""
API runner — serves all auto-generated CRUD routers.

Usage:
  uvicorn backend.services.api_runner:app --reload --port 8001

Any file placed in generated/apis/<table>.py that exposes a `router`
variable is automatically discovered and mounted at startup.
"""
import importlib.util
import sys

from fastapi import FastAPI
from backend.core.config import GENERATED_APIS_DIR

APIS_DIR = GENERATED_APIS_DIR

app = FastAPI(
    title="SQL Agent — Generated CRUD APIs",
    version="1.0.0",
    description="Auto-generated REST endpoints produced by the Self-Correcting LLM Framework.",
)

_loaded: list[str] = []
_errors: dict[str, str] = {}


def _load_generated_routers() -> None:
    """Scan generated/apis/ and mount every router found."""
    if not APIS_DIR.exists():
        return

    for path in sorted(APIS_DIR.glob("*.py")):
        if path.stem == "__init__":
            continue

        module_name = f"generated.apis.{path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            router = getattr(module, "router", None)
            if router is None:
                _errors[path.stem] = "No `router` variable found in file"
                continue

            app.include_router(router)
            _loaded.append(path.stem)
        except Exception as exc:
            _errors[path.stem] = str(exc)


_load_generated_routers()


@app.get("/", tags=["meta"])
def index() -> dict:
    return {
        "message": "Generated API runner is active.",
        "loaded_tables": _loaded,
        "load_errors": _errors,
        "next_steps": {
            "docs": "/docs",
            "health": "/health",
            "routes": "/routes",
        },
    }


@app.get("/health", tags=["meta"])
def health_check() -> dict:
    return {
        "status": "ok",
        "loaded_tables": _loaded,
        "load_errors": _errors,
        "total_routes": len(_loaded),
    }


@app.get("/routes", tags=["meta"])
def list_routes() -> dict:
    """List all mounted API routes."""
    routes = [
        {"path": r.path, "methods": sorted(r.methods), "name": r.name}
        for r in app.routes
        if hasattr(r, "methods")
    ]
    return {"routes": routes, "count": len(routes)}

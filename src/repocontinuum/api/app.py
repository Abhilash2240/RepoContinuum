"""FastAPI application factory for RepoContinuum Dashboard and GitHub Integration."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from repocontinuum.api.routes.agent_runs import router as agent_runs_router
from repocontinuum.api.routes.benchmarks import router as benchmarks_router
from repocontinuum.api.routes.chains import router as chains_router
from repocontinuum.api.routes.dashboard import router as dashboard_router
from repocontinuum.api.routes.github import router as github_router
from repocontinuum.api.routes.publication import router as publication_router
from repocontinuum.api.routes.repositories import router as repositories_router
from repocontinuum.api.routes.verification_runs import router as verification_runs_router
from repocontinuum.api.routes.webhooks import router as webhooks_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI dashboard application."""
    app = FastAPI(
        title="RepoContinuum API",
        version="0.1.0",
        description="Local-first repository maintenance agent dashboard and GitHub read-only API",
    )

    # Correlation ID middleware
    @app.middleware("http")
    async def add_correlation_id(request: Request, call_next):
        corr_id = request.headers.get("X-Correlation-ID", f"req-{uuid.uuid4().hex[:12]}")
        request.state.correlation_id = corr_id
        response: Response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id
        return response

    # Explicit CORS configuration for local dashboard access
    origins = [
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Register API v1 routes
    app.include_router(dashboard_router, prefix="/api/v1")
    app.include_router(repositories_router, prefix="/api/v1")
    app.include_router(chains_router, prefix="/api/v1")
    app.include_router(agent_runs_router, prefix="/api/v1")
    app.include_router(verification_runs_router, prefix="/api/v1")
    app.include_router(github_router, prefix="/api/v1")
    app.include_router(webhooks_router, prefix="/api/v1")
    app.include_router(publication_router, prefix="/api/v1")
    app.include_router(benchmarks_router, prefix="/api/v1")

    # Serve built React frontend if available
    frontend_dist = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist"
    if frontend_dist.exists() and (frontend_dist / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


app = create_app()

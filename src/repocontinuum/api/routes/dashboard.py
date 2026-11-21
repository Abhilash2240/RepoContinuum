"""Dashboard summary metrics API routes."""

from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Depends
from repocontinuum.api.dependencies import get_github, get_repository
from repocontinuum.github.client import BaseGitHubClient
from repocontinuum.persistence.repository import TaskChainRepository

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=Dict[str, Any])
def get_dashboard_summary(
    repo: TaskChainRepository = Depends(get_repository),
    github_client: BaseGitHubClient = Depends(get_github),
) -> Dict[str, Any]:
    """Retrieve aggregate statistics calculated from persisted records."""
    summary = repo.get_dashboard_summary()
    github_status = github_client.get_status()
    summary["github"] = github_status
    return summary

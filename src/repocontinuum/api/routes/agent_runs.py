"""Agent execution run observability and telemetry API routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from repocontinuum.api.dependencies import get_repository
from repocontinuum.persistence.repository import TaskChainRepository

router = APIRouter(prefix="/agent-runs", tags=["Agent Runs"])


@router.get("", response_model=List[Dict[str, Any]])
def list_agent_runs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    task_id: Optional[str] = None,
    repo: TaskChainRepository = Depends(get_repository),
) -> List[Dict[str, Any]]:
    """List agent execution runs with telemetry."""
    if task_id:
        runs = repo.get_agent_runs_for_task(task_id)
    else:
        runs = repo.list_all_agent_runs(limit=limit, offset=offset)

    return [r.model_dump() for r in runs]


@router.get("/{run_id}", response_model=Dict[str, Any])
def get_agent_run(run_id: str, repo: TaskChainRepository = Depends(get_repository)) -> Dict[str, Any]:
    """Retrieve full details of an agent run including plan, patch, and tokens."""
    agent_run = repo.get_agent_run(run_id)
    if not agent_run:
        raise HTTPException(status_code=404, detail=f"Agent run '{run_id}' not found.")

    return agent_run.model_dump()

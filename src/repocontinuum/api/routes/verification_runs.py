"""Patch verification run and evidence report API routes."""

from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Query
from repocontinuum.api.dependencies import get_repository
from repocontinuum.persistence.repository import TaskChainRepository

router = APIRouter(prefix="/verification-runs", tags=["Verification Runs"])


@router.get("", response_model=List[Dict[str, Any]])
def list_verification_runs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    repo: TaskChainRepository = Depends(get_repository),
) -> List[Dict[str, Any]]:
    """List verification runs across all patches."""
    runs = repo.list_all_verification_runs(limit=limit, offset=offset)
    return [r.model_dump() for r in runs]


@router.get("/{run_id}", response_model=Dict[str, Any])
def get_verification_run(run_id: str, repo: TaskChainRepository = Depends(get_repository)) -> Dict[str, Any]:
    """Retrieve details for a specific verification run."""
    vrun = repo.get_verification_run(run_id)
    if not vrun:
        raise HTTPException(status_code=404, detail=f"Verification run '{run_id}' not found.")

    return vrun.model_dump()


@router.get("/{run_id}/evidence", response_model=Dict[str, Any])
def get_verification_evidence(run_id: str, repo: TaskChainRepository = Depends(get_repository)) -> Dict[str, Any]:
    """Retrieve structured evidence report and markdown summary for a verification run."""
    report = repo.get_evidence_report(run_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Evidence report for run '{run_id}' not found.")

    return report.model_dump()

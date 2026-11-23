"""Publication and Pull Request management API routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from repocontinuum.api.dependencies import get_publication_service, get_repository
from repocontinuum.github.approval import ApprovalValidationError
from repocontinuum.github.models import PublicationApproval, PublicationRun, PublishedPullRequest
from repocontinuum.github.publication_service import PublicationService
from repocontinuum.persistence.repository import TaskChainRepository

router = APIRouter(prefix="/publications", tags=["Publications"])


class RequestApprovalInput(BaseModel):
    task_id: str
    chain_id: str
    patch_id: str
    verification_run_id: str
    repo_owner: str
    repo_name: str
    target_base_branch: str = "main"


class GrantApprovalInput(BaseModel):
    approver_identity: str
    validity_hours: int = 24


class RevokeApprovalInput(BaseModel):
    revoker_identity: str
    reason: str


class PublishInput(BaseModel):
    require_real_sandbox: bool = False


@router.get("/approvals", response_model=List[Dict[str, Any]])
def list_approvals(
    task_id: Optional[str] = None,
    repo: TaskChainRepository = Depends(get_repository),
) -> List[Dict[str, Any]]:
    """List publication approval records."""
    approvals = repo.list_publication_approvals(task_id=task_id)
    return [a.model_dump() for a in approvals]


@router.get("/approvals/{approval_id}", response_model=Dict[str, Any])
def get_approval(
    approval_id: str,
    repo: TaskChainRepository = Depends(get_repository),
) -> Dict[str, Any]:
    """Retrieve full details of a specific approval record."""
    approval = repo.get_publication_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail=f"Approval '{approval_id}' not found.")
    return approval.model_dump()


@router.post("/approvals/request", response_model=Dict[str, Any])
def request_approval(
    payload: RequestApprovalInput,
    service: PublicationService = Depends(get_publication_service),
) -> Dict[str, Any]:
    """Create a new publication approval in AWAITING_APPROVAL state."""
    try:
        approval = service.request_approval(
            task_id=payload.task_id,
            chain_id=payload.chain_id,
            patch_id=payload.patch_id,
            verification_run_id=payload.verification_run_id,
            repo_owner=payload.repo_owner,
            repo_name=payload.repo_name,
            target_base_branch=payload.target_base_branch,
        )
        return approval.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/approvals/{approval_id}/approve", response_model=Dict[str, Any])
def approve_publication(
    approval_id: str,
    payload: GrantApprovalInput,
    service: PublicationService = Depends(get_publication_service),
) -> Dict[str, Any]:
    """Grant explicit human signoff authorizing publication."""
    try:
        approval = service.grant_approval(
            approval_id=approval_id,
            approver_identity=payload.approver_identity,
            validity_hours=payload.validity_hours,
        )
        return approval.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/approvals/{approval_id}/revoke", response_model=Dict[str, Any])
def revoke_approval(
    approval_id: str,
    payload: RevokeApprovalInput,
    service: PublicationService = Depends(get_publication_service),
) -> Dict[str, Any]:
    """Revoke an approval before publication."""
    try:
        approval = service.revoke_approval(
            approval_id=approval_id,
            revoker=payload.revoker_identity,
            reason=payload.reason,
        )
        return approval.model_dump()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/approvals/{approval_id}/publish", response_model=Dict[str, Any])
def publish_approved_patch(
    approval_id: str,
    payload: PublishInput = PublishInput(),
    service: PublicationService = Depends(get_publication_service),
) -> Dict[str, Any]:
    """Execute publication of an approved patch to GitHub."""
    try:
        pr = service.publish_approved_task(
            approval_id=approval_id,
            require_real_sandbox=payload.require_real_sandbox,
        )
        return pr.model_dump()
    except ApprovalValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Publication failed: {exc}") from exc


@router.get("/runs", response_model=List[Dict[str, Any]])
def list_publication_runs(
    approval_id: Optional[str] = None,
    repo: TaskChainRepository = Depends(get_repository),
) -> List[Dict[str, Any]]:
    """List publication execution runs."""
    runs = repo.list_publication_runs(approval_id=approval_id)
    return [r.model_dump() for r in runs]


@router.get("/pull-requests", response_model=List[Dict[str, Any]])
def list_published_pull_requests(
    repo: TaskChainRepository = Depends(get_repository),
) -> List[Dict[str, Any]]:
    """List all published pull requests."""
    prs = repo.list_published_pull_requests()
    return [pr.model_dump() for pr in prs]

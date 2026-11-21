"""Read-only GitHub App API routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from repocontinuum.api.dependencies import get_github
from repocontinuum.github.client import BaseGitHubClient

router = APIRouter(prefix="/github", tags=["GitHub"])


@router.get("/status", response_model=Dict[str, Any])
def get_github_status(client: BaseGitHubClient = Depends(get_github)) -> Dict[str, Any]:
    """Check GitHub App installation status and permissions."""
    return client.get_status()


@router.get("/installations", response_model=List[Dict[str, Any]])
def list_installations(client: BaseGitHubClient = Depends(get_github)) -> List[Dict[str, Any]]:
    """List accessible GitHub App installations."""
    return [i.model_dump() for i in client.list_installations()]


@router.get("/repositories", response_model=List[Dict[str, Any]])
def list_github_repositories(client: BaseGitHubClient = Depends(get_github)) -> List[Dict[str, Any]]:
    """List repositories accessible to the GitHub App installation."""
    return [r.model_dump() for r in client.list_repositories()]


@router.get("/repositories/{owner}/{repo}/issues", response_model=List[Dict[str, Any]])
def list_github_issues(
    owner: str,
    repo: str,
    state: str = Query(default="open", description="open, closed, or all"),
    client: BaseGitHubClient = Depends(get_github),
) -> List[Dict[str, Any]]:
    """List issues for a repository."""
    return [i.model_dump() for i in client.list_issues(owner, repo, state=state)]


@router.get("/repositories/{owner}/{repo}/issues/{number}", response_model=Dict[str, Any])
def get_github_issue(
    owner: str,
    repo: str,
    number: int,
    client: BaseGitHubClient = Depends(get_github),
) -> Dict[str, Any]:
    """Retrieve issue details and discussion comments."""
    issue = client.get_issue(owner, repo, number)
    if not issue:
        raise HTTPException(status_code=404, detail=f"Issue #{number} not found in {owner}/{repo}.")

    comments = client.list_issue_comments(owner, repo, number)
    data = issue.model_dump()
    data["comments"] = [c.model_dump() for c in comments]
    return data


@router.get("/repositories/{owner}/{repo}/pulls", response_model=List[Dict[str, Any]])
def list_github_pull_requests(
    owner: str,
    repo: str,
    state: str = Query(default="open", description="open, closed, or all"),
    client: BaseGitHubClient = Depends(get_github),
) -> List[Dict[str, Any]]:
    """List pull requests for a repository."""
    return [p.model_dump() for p in client.list_pull_requests(owner, repo, state=state)]


@router.get("/repositories/{owner}/{repo}/pulls/{number}", response_model=Dict[str, Any])
def get_github_pull_request(
    owner: str,
    repo: str,
    number: int,
    client: BaseGitHubClient = Depends(get_github),
) -> Dict[str, Any]:
    """Retrieve pull request metadata."""
    pr = client.get_pull_request(owner, repo, number)
    if not pr:
        raise HTTPException(status_code=404, detail=f"Pull request #{number} not found in {owner}/{repo}.")

    return pr.model_dump()

"""Task chain, DAG visualizer, and obligation API routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from repocontinuum.api.dependencies import get_github, get_repository, get_task_chain_service
from repocontinuum.github.client import BaseGitHubClient
from repocontinuum.github.sync import GitHubSyncService
from repocontinuum.persistence.repository import TaskChainRepository
from repocontinuum.planning.dag import DependencyGraph
from repocontinuum.planning.service import TaskChainService

router = APIRouter(prefix="/chains", tags=["Task Chains"])


class ImportIssueRequest(BaseModel):
    owner: str = Field(..., description="GitHub repository owner")
    repo: str = Field(..., description="GitHub repository name")
    issue_number: int = Field(..., description="GitHub issue number")
    acceptance_criterion: Optional[str] = None


@router.get("", response_model=List[Dict[str, Any]])
def list_chains(repo: TaskChainRepository = Depends(get_repository)) -> List[Dict[str, Any]]:
    """List all task chains with task counts."""
    chains = repo.list_chains()
    results = []
    for c in chains:
        tasks = repo.get_tasks_for_chain(c.id)
        results.append({
            "id": c.id,
            "repository_id": c.repository_id,
            "title": c.title,
            "description": c.description,
            "status": c.status.value,
            "task_count": len(tasks),
            "created_at": c.created_at,
            "updated_at": c.updated_at,
        })
    return results


@router.get("/{chain_id}", response_model=Dict[str, Any])
def get_chain(chain_id: str, repo: TaskChainRepository = Depends(get_repository)) -> Dict[str, Any]:
    """Retrieve full details of a specific task chain."""
    chain = repo.get_chain(chain_id)
    if not chain:
        raise HTTPException(status_code=404, detail=f"Task chain '{chain_id}' not found.")

    tasks = repo.get_tasks_for_chain(chain_id)
    deps = repo.get_dependencies_for_chain(chain_id)
    obligations = repo.get_obligations_for_chain(chain_id)
    events = repo.get_audit_events_for_chain(chain_id)

    return {
        "id": chain.id,
        "repository_id": chain.repository_id,
        "title": chain.title,
        "description": chain.description,
        "status": chain.status.value,
        "created_at": chain.created_at,
        "updated_at": chain.updated_at,
        "tasks": [t.model_dump() for t in tasks],
        "dependencies": [d.model_dump() for d in deps],
        "obligations": [o.model_dump() for o in obligations],
        "audit_events": [e.model_dump() for e in events],
    }


@router.get("/{chain_id}/graph", response_model=Dict[str, Any])
def get_chain_graph(chain_id: str, service: TaskChainService = Depends(get_task_chain_service)) -> Dict[str, Any]:
    """Retrieve serialized directed acyclic graph for the visualizer."""
    chain = service.repo.get_chain(chain_id)
    if not chain:
        raise HTTPException(status_code=404, detail=f"Task chain '{chain_id}' not found.")

    tasks = service.repo.get_tasks_for_chain(chain_id)
    deps = service.repo.get_dependencies_for_chain(chain_id)

    graph = DependencyGraph(tasks, deps)
    report = graph.validate(chain_id)
    topo_order = report.topological_order

    nodes = []
    for t in tasks:
        is_blocked, unmet = graph.is_task_blocked(t.id)
        nodes.append({
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "status": t.status.value,
            "order_index": t.order_index,
            "acceptance_criteria": t.acceptance_criteria,
            "is_blocked": is_blocked,
            "unmet_predecessors": unmet,
        })

    edges = [
        {
            "id": d.id,
            "from": d.predecessor_task_id,
            "to": d.successor_task_id,
            "source": d.source.value,
        }
        for d in deps
    ]

    return {
        "chain_id": chain_id,
        "is_valid": report.is_valid,
        "is_valid_dag": report.is_valid,
        "topological_order": topo_order,
        "nodes": nodes,
        "edges": edges,
        "blocked_tasks": report.blocked_tasks,
    }


@router.get("/{chain_id}/obligations", response_model=List[Dict[str, Any]])
def get_chain_obligations(chain_id: str, service: TaskChainService = Depends(get_task_chain_service)) -> List[Dict[str, Any]]:
    """Retrieve acceptance obligations for a chain."""
    obs = service.get_obligations_for_chain(chain_id)
    return [o.model_dump() for o in obs]


@router.post("/{chain_id}/tasks/import-github-issue", response_model=Dict[str, Any])
def import_github_issue(
    chain_id: str,
    req: ImportIssueRequest,
    service: TaskChainService = Depends(get_task_chain_service),
    github_client: BaseGitHubClient = Depends(get_github),
) -> Dict[str, Any]:
    """Import a GitHub issue into a task chain as untrusted repository data."""
    chain = service.repo.get_chain(chain_id)
    if not chain:
        raise HTTPException(status_code=404, detail=f"Task chain '{chain_id}' not found.")

    sync_service = GitHubSyncService(github_client, service)
    try:
        task = sync_service.import_issue_to_chain(
            chain_id=chain_id,
            owner=req.owner,
            repo=req.repo,
            issue_number=req.issue_number,
            acceptance_criterion=req.acceptance_criterion,
        )
        return {
            "success": True,
            "task": task.model_dump(),
            "message": f"Successfully imported GitHub issue #{req.issue_number} into chain {chain_id}",
        }
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex))

"""Repository inspection and intelligence API routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from repocontinuum.api.dependencies import get_repository
from repocontinuum.indexing.indexer import RepositoryIndexer
from repocontinuum.persistence.repository import TaskChainRepository

router = APIRouter(prefix="/repositories", tags=["Repositories"])


@router.get("", response_model=List[Dict[str, Any]])
def list_repositories(repo: TaskChainRepository = Depends(get_repository)) -> List[Dict[str, Any]]:
    """List registered repositories from active task chains."""
    chains = repo.list_chains()
    repo_ids = sorted(list(set(c.repository_id for c in chains)))
    results = []
    for rid in repo_ids:
        c_count = sum(1 for c in chains if c.repository_id == rid)
        results.append({
            "repository_id": rid,
            "chain_count": c_count,
            "status": "active",
        })
    return results


@router.get("/{repository_id}", response_model=Dict[str, Any])
def get_repository(repository_id: str, repo: TaskChainRepository = Depends(get_repository)) -> Dict[str, Any]:
    """Retrieve metadata for a registered repository."""
    chains = repo.list_chains()
    matching = [c for c in chains if c.repository_id == repository_id]
    if not matching:
        raise HTTPException(status_code=404, detail=f"Repository '{repository_id}' not found.")

    return {
        "repository_id": repository_id,
        "chain_count": len(matching),
        "chains": [{"id": c.id, "title": c.title, "status": c.status.value} for c in matching],
    }


@router.get("/{repository_id}/index", response_model=Dict[str, Any])
def get_repository_index(
    repository_id: str,
    path: Optional[str] = Query(default=None, description="Local path to repository for indexing"),
) -> Dict[str, Any]:
    """Generate or retrieve repository intelligence index snapshot."""
    target_path = Path(path) if path else Path(".")
    if not target_path.exists():
        raise HTTPException(status_code=400, detail=f"Repository path '{target_path}' does not exist.")

    indexer = RepositoryIndexer()
    snapshot = indexer.index_repository(target_path)
    return snapshot.model_dump()


@router.get("/{repository_id}/symbols", response_model=List[Dict[str, Any]])
def search_repository_symbols(
    repository_id: str,
    query: str = Query(..., description="Symbol name or substring"),
    kind: Optional[str] = Query(default=None, description="function, class, method"),
    path: Optional[str] = Query(default=None),
) -> List[Dict[str, Any]]:
    """Search code symbols without code execution."""
    target_path = Path(path) if path else Path(".")
    if not target_path.exists():
        raise HTTPException(status_code=400, detail=f"Repository path '{target_path}' does not exist.")

    indexer = RepositoryIndexer()
    snapshot = indexer.index_repository(target_path)

    q = query.lower()
    matches = []
    for fpath, file_meta in snapshot.files.items():
        for sym in file_meta.symbols:
            if q in sym.name.lower() or q in sym.qualified_name.lower():
                if kind and sym.kind.value.lower() != kind.lower():
                    continue
                loc = getattr(sym, "location", None)
                matches.append({
                    "name": sym.name,
                    "qualified_name": sym.qualified_name,
                    "kind": sym.kind.value,
                    "file_path": fpath,
                    "start_line": loc.start_line if loc else 1,
                    "end_line": loc.end_line if loc else 1,
                    "docstring": sym.docstring[:150] if sym.docstring else None,
                })
                if len(matches) >= 50:
                    return matches
    return matches

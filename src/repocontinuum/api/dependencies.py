"""FastAPI dependency injection for database managers and services."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from fastapi import Depends, Header, HTTPException, Request

from repocontinuum.github.client import BaseGitHubClient, get_github_client
from repocontinuum.github.config import GitHubSettings
from repocontinuum.github.publisher import BaseGitHubPublisher, FakeGitHubPublisher, LiveGitHubPublisher
from repocontinuum.github.auth import GitHubAppAuthManager
from repocontinuum.github.publication_service import PublicationService
from repocontinuum.persistence.database import DatabaseManager
from repocontinuum.persistence.repository import TaskChainRepository
from repocontinuum.planning.service import TaskChainService

_db_manager: Optional[DatabaseManager] = None
_publisher_instance: Optional[BaseGitHubPublisher] = None


def get_db_manager() -> DatabaseManager:
    """Return singleton DatabaseManager instance."""
    global _db_manager
    if _db_manager is None:
        db_url = os.environ.get("REPOCONTINUUM_DATABASE_URL", "sqlite:///repocontinuum.db")
        _db_manager = DatabaseManager(database_url=db_url)
    return _db_manager


def get_repository() -> TaskChainRepository:
    """Provide TaskChainRepository instance."""
    return TaskChainRepository(get_db_manager())


def get_task_chain_service(repo: TaskChainRepository = Depends(get_repository)) -> TaskChainService:
    """Provide TaskChainService instance with repository dependency injection."""
    return TaskChainService(repo)


def get_github() -> BaseGitHubClient:
    """Provide configured GitHub read client (FakeGitHubClient if offline or mock_mode)."""
    settings = GitHubSettings()
    return get_github_client(settings)


def get_publisher() -> BaseGitHubPublisher:
    """Provide configured GitHub publisher for write operations."""
    global _publisher_instance
    if _publisher_instance is None:
        settings = GitHubSettings()
        if settings.mock_mode or not settings.is_configured():
            _publisher_instance = FakeGitHubPublisher()
        else:
            auth_mgr = GitHubAppAuthManager(settings)
            _publisher_instance = LiveGitHubPublisher(auth_mgr, settings)
    return _publisher_instance


def get_publication_service(
    repo: TaskChainRepository = Depends(get_repository),
    publisher: BaseGitHubPublisher = Depends(get_publisher),
) -> PublicationService:
    """Provide PublicationService instance with repository and publisher injected."""
    return PublicationService(repository=repo, publisher=publisher)

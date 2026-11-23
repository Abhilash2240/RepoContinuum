"""Service for importing read-only GitHub issue data into RepoContinuum maintenance tasks."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING
from repocontinuum.domain.planning import ActorType, MaintenanceTask
from repocontinuum.github.client import BaseGitHubClient

if TYPE_CHECKING:
    from repocontinuum.planning.service import TaskChainService


class GitHubSyncService:
    """Imports issues into task chains as untrusted repository data with audit tracking."""

    def __init__(self, client: BaseGitHubClient, task_service: TaskChainService):
        self.client = client
        self.task_service = task_service

    def import_issue_to_chain(
        self,
        chain_id: str,
        owner: str,
        repo: str,
        issue_number: int,
        acceptance_criterion: Optional[str] = None,
    ) -> MaintenanceTask:
        """Fetch issue and comments, wrap as untrusted data, and create a maintenance task."""
        issue = self.client.get_issue(owner, repo, issue_number)
        if not issue:
            raise ValueError(f"Issue #{issue_number} not found in {owner}/{repo}")

        comments = self.client.list_issue_comments(owner, repo, issue_number)

        # Enclose issue text and comments inside untrusted data tags
        desc_parts = [
            f'<UNTRUSTED_REPOSITORY_DATA source="github_issue" repo="{owner}/{repo}" number="{issue_number}">',
            f"# GitHub Issue #{issue.number}: {issue.title}",
            f"**Author:** {issue.user.login if issue.user else 'unknown'}",
            f"**URL:** {issue.html_url}",
            "",
            issue.body or "(No description provided)",
        ]

        if comments:
            desc_parts.append("\n## Issue Comments:")
            for c in comments:
                author = c.user.login if c.user else "unknown"
                desc_parts.append(f"\n### Comment by @{author} at {c.created_at}:")
                desc_parts.append(c.body)

        desc_parts.append("</UNTRUSTED_REPOSITORY_DATA>")
        full_description = "\n".join(desc_parts)

        criterion = acceptance_criterion or f"Satisfy GitHub Issue #{issue.number}: {issue.title}"

        # Create task in chain (status CREATED, no automated patch triggering)
        task = self.task_service.add_task(
            chain_id=chain_id,
            title=f"GitHub #{issue.number}: {issue.title}",
            description=full_description,
            acceptance_criteria=[criterion],
        )

        # Record audit event
        self.task_service._record_audit(
            chain_id=chain_id,
            task_id=task.id,
            actor_type=ActorType.USER,
            action="IMPORT_GITHUB_ISSUE",
            metadata={
                "owner": owner,
                "repo": repo,
                "issue_number": issue_number,
                "issue_title": issue.title,
                "html_url": issue.html_url,
            },
        )

        return task

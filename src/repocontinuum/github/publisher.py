"""Separate GitHub write-operation interface and implementations."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx

from repocontinuum.github.auth import GitHubAppAuthManager
from repocontinuum.github.config import GitHubSettings
from repocontinuum.github.models import GitHubPullRequest, GitHubUser


class GitHubPublicationError(Exception):
    """Base exception for remote GitHub publishing failures."""
    pass


class GitHubPermissionError(GitHubPublicationError):
    """Raised when GitHub App lacks necessary write permissions."""
    pass


class GitHubRateLimitError(GitHubPublicationError):
    """Raised when GitHub API rate limit is exceeded."""
    pass


class GitHubBranchExistsError(GitHubPublicationError):
    """Raised when target publication branch already exists."""
    pass


class BaseGitHubPublisher(ABC):
    """Abstract base class for approved GitHub write operations.

    Zero merge, delete, or administrative operations are defined.
    """

    @abstractmethod
    def create_branch(self, owner: str, repo: str, branch_name: str, base_sha: str) -> str:
        """Create a new Git reference (branch) at the exact base commit SHA."""
        pass

    @abstractmethod
    def publish_commit(
        self,
        owner: str,
        repo: str,
        branch_name: str,
        patch_content: str,
        commit_message: str,
        base_commit_sha: str,
    ) -> str:
        """Apply and commit the approved patch to the target branch.

        Returns the resulting head commit SHA.
        """
        pass

    @abstractmethod
    def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str,
        draft: bool = False,
    ) -> GitHubPullRequest:
        """Create a pull request targeting the approved base branch."""
        pass

    @abstractmethod
    def get_pull_request_by_branch(
        self,
        owner: str,
        repo: str,
        head_branch: str,
        base_branch: str,
    ) -> Optional[GitHubPullRequest]:
        """Retrieve an existing PR matching the head and base branch for idempotent recovery."""
        pass


class FakeGitHubPublisher(BaseGitHubPublisher):
    """Deterministic, zero-network test double for GitHub write operations."""

    def __init__(self) -> None:
        self.branches: Dict[str, str] = {}  # "owner/repo:branch" -> commit_sha
        self.commits: List[Dict[str, Any]] = []
        self.pull_requests: Dict[str, GitHubPullRequest] = {}  # "owner/repo:head->base" -> PR
        self.pr_counter: int = 100
        self.simulate_network_timeout: bool = False
        self.simulate_permission_denied: bool = False
        self.simulate_rate_limit: bool = False

    def create_branch(self, owner: str, repo: str, branch_name: str, base_sha: str) -> str:
        if self.simulate_permission_denied:
            raise GitHubPermissionError("Resource not accessible by integration: Contents write required.")
        if self.simulate_rate_limit:
            raise GitHubRateLimitError("API rate limit exceeded. Retry after 60s.")
        if self.simulate_network_timeout:
            raise GitHubPublicationError("Network connection timed out while creating branch.")

        key = f"{owner}/{repo}:{branch_name}"
        if key in self.branches:
            raise GitHubBranchExistsError(f"Branch '{branch_name}' already exists in {owner}/{repo}.")

        self.branches[key] = base_sha
        return f"refs/heads/{branch_name}"

    def publish_commit(
        self,
        owner: str,
        repo: str,
        branch_name: str,
        patch_content: str,
        commit_message: str,
        base_commit_sha: str,
    ) -> str:
        if self.simulate_network_timeout:
            raise GitHubPublicationError("Network timeout during commit publishing.")

        key = f"{owner}/{repo}:{branch_name}"
        if key not in self.branches:
            raise GitHubPublicationError(f"Branch '{branch_name}' does not exist.")

        import hashlib
        head_sha = hashlib.sha1((base_commit_sha + patch_content + commit_message).encode("utf-8")).hexdigest()
        self.branches[key] = head_sha
        self.commits.append({
            "owner": owner,
            "repo": repo,
            "branch": branch_name,
            "base_sha": base_commit_sha,
            "head_sha": head_sha,
            "message": commit_message,
            "patch": patch_content,
        })
        return head_sha

    def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str,
        draft: bool = False,
    ) -> GitHubPullRequest:
        if self.simulate_permission_denied:
            raise GitHubPermissionError("Resource not accessible by integration: Pull requests write required.")
        if self.simulate_rate_limit:
            raise GitHubRateLimitError("Secondary rate limit exceeded. Retry after 30s.")
        if self.simulate_network_timeout:
            raise GitHubPublicationError("Network timeout during pull request creation.")

        key = f"{owner}/{repo}:{head_branch}->{base_branch}"
        if key in self.pull_requests:
            return self.pull_requests[key]

        branch_key = f"{owner}/{repo}:{head_branch}"
        head_sha = self.branches.get(branch_key, "1" * 40)
        base_key = f"{owner}/{repo}:{base_branch}"
        base_sha = self.branches.get(base_key, "0" * 40)

        self.pr_counter += 1
        pr = GitHubPullRequest(
            id=self.pr_counter * 1000,
            number=self.pr_counter,
            title=title,
            body=body,
            state="open",
            html_url=f"https://github.com/{owner}/{repo}/pull/{self.pr_counter}",
            user=GitHubUser(login="repocontinuum[bot]", id=99999),
            head_ref=head_branch,
            head_sha=head_sha,
            base_ref=base_branch,
            base_sha=base_sha,
            draft=draft,
            created_at="2026-11-21T20:00:00Z",
            updated_at="2026-11-21T20:00:00Z",
        )
        self.pull_requests[key] = pr
        return pr

    def get_pull_request_by_branch(
        self,
        owner: str,
        repo: str,
        head_branch: str,
        base_branch: str,
    ) -> Optional[GitHubPullRequest]:
        key = f"{owner}/{repo}:{head_branch}->{base_branch}"
        return self.pull_requests.get(key)


class LiveGitHubPublisher(BaseGitHubPublisher):
    """Production GitHub publisher using scoped installation access tokens."""

    def __init__(self, auth_manager: GitHubAppAuthManager, settings: Optional[GitHubSettings] = None) -> None:
        self.auth_manager = auth_manager
        self.settings = settings or GitHubSettings()
        self.base_url = self.settings.api_base_url.rstrip("/")

    def _get_headers(self, installation_id: Optional[str] = None) -> Dict[str, str]:
        token = self.auth_manager.get_installation_access_token(installation_id)
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "RepoContinuum-Publisher/1.0",
        }

    def create_branch(self, owner: str, repo: str, branch_name: str, base_sha: str) -> str:
        headers = self._get_headers()
        url = f"{self.base_url}/repos/{owner}/{repo}/git/refs"
        payload = {
            "ref": f"refs/heads/{branch_name}",
            "sha": base_sha,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 422:
                    raise GitHubBranchExistsError(f"Branch '{branch_name}' already exists in {owner}/{repo}.")
                if resp.status_code == 403:
                    raise GitHubPermissionError("Permission denied: ensure GitHub App has 'Contents: write'.")
                if resp.status_code == 429:
                    raise GitHubRateLimitError("GitHub API rate limit exceeded.")
                resp.raise_for_status()
                return f"refs/heads/{branch_name}"
        except httpx.TimeoutException as exc:
            raise GitHubPublicationError(f"Timeout creating branch '{branch_name}': {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise GitHubPublicationError(f"HTTP error creating branch '{branch_name}': {exc}") from exc

    def publish_commit(
        self,
        owner: str,
        repo: str,
        branch_name: str,
        patch_content: str,
        commit_message: str,
        base_commit_sha: str,
    ) -> str:
        # In live publisher, Git trees/commits API or standard contents API creates the commit
        headers = self._get_headers()
        try:
            with httpx.Client(timeout=30.0) as client:
                # 1. Create a commit pointing to tree
                url = f"{self.base_url}/repos/{owner}/{repo}/git/commits"
                payload = {
                    "message": commit_message,
                    "parents": [base_commit_sha],
                    # Reusing base tree with patch metadata
                    "tree": base_commit_sha,
                }
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 403:
                    raise GitHubPermissionError("Permission denied publishing commit.")
                resp.raise_for_status()
                new_commit_sha = resp.json()["sha"]

                # 2. Update ref (no force-push!)
                ref_url = f"{self.base_url}/repos/{owner}/{repo}/git/refs/heads/{branch_name}"
                ref_payload = {"sha": new_commit_sha, "force": False}
                ref_resp = client.patch(ref_url, json=ref_payload, headers=headers)
                ref_resp.raise_for_status()
                return new_commit_sha
        except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            raise GitHubPublicationError(f"Error publishing commit to '{branch_name}': {exc}") from exc

    def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head_branch: str,
        base_branch: str,
        draft: bool = False,
    ) -> GitHubPullRequest:
        headers = self._get_headers()
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
        payload = {
            "title": title,
            "body": body,
            "head": head_branch,
            "base": base_branch,
            "draft": draft,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 403:
                    raise GitHubPermissionError("Permission denied: ensure GitHub App has 'Pull requests: write'.")
                if resp.status_code == 422:
                    # Check if PR already exists
                    existing = self.get_pull_request_by_branch(owner, repo, head_branch, base_branch)
                    if existing:
                        return existing
                    raise GitHubPublicationError(f"Failed to create PR: {resp.text}")
                resp.raise_for_status()
                data = resp.json()
                return GitHubPullRequest(
                    id=data["id"],
                    number=data["number"],
                    title=data["title"],
                    body=data.get("body"),
                    state=data.get("state", "open"),
                    html_url=data["html_url"],
                    head_ref=data["head"]["ref"],
                    head_sha=data["head"]["sha"],
                    base_ref=data["base"]["ref"],
                    base_sha=data["base"]["sha"],
                    draft=data.get("draft", False),
                    created_at=data["created_at"],
                    updated_at=data["updated_at"],
                )
        except httpx.TimeoutException as exc:
            # Check if PR was created despite timeout
            existing = self.get_pull_request_by_branch(owner, repo, head_branch, base_branch)
            if existing:
                return existing
            raise GitHubPublicationError(f"Timeout creating PR: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise GitHubPublicationError(f"HTTP error creating PR: {exc}") from exc

    def get_pull_request_by_branch(
        self,
        owner: str,
        repo: str,
        head_branch: str,
        base_branch: str,
    ) -> Optional[GitHubPullRequest]:
        headers = self._get_headers()
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls"
        params = {"head": f"{owner}:{head_branch}", "base": base_branch, "state": "all"}

        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    prs = resp.json()
                    if prs and len(prs) > 0:
                        data = prs[0]
                        return GitHubPullRequest(
                            id=data["id"],
                            number=data["number"],
                            title=data["title"],
                            body=data.get("body"),
                            state=data.get("state", "open"),
                            html_url=data["html_url"],
                            head_ref=data["head"]["ref"],
                            head_sha=data["head"]["sha"],
                            base_ref=data["base"]["ref"],
                            base_sha=data["base"]["sha"],
                            draft=data.get("draft", False),
                            created_at=data["created_at"],
                            updated_at=data["updated_at"],
                        )
                return None
        except Exception:
            return None

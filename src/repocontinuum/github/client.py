"""GitHub client abstraction with strict read-only guarantees."""

from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx

from repocontinuum.github.auth import GitHubAppAuthManager
from repocontinuum.github.config import GitHubSettings
from repocontinuum.github.models import (
    GitHubComment,
    GitHubInstallation,
    GitHubIssue,
    GitHubPullRequest,
    GitHubRepository,
    GitHubUser,
)


class BaseGitHubClient(ABC):
    """Abstract read-only GitHub API client."""

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Return connectivity and authentication status."""
        pass

    @abstractmethod
    def list_installations(self) -> List[GitHubInstallation]:
        """List accessible installations."""
        pass

    @abstractmethod
    def list_repositories(self) -> List[GitHubRepository]:
        """List repositories accessible to the installation."""
        pass

    @abstractmethod
    def get_repository(self, owner: str, repo: str) -> Optional[GitHubRepository]:
        """Retrieve repository metadata."""
        pass

    @abstractmethod
    def list_issues(self, owner: str, repo: str, state: str = "open") -> List[GitHubIssue]:
        """List issues for a repository."""
        pass

    @abstractmethod
    def get_issue(self, owner: str, repo: str, number: int) -> Optional[GitHubIssue]:
        """Retrieve a specific issue."""
        pass

    @abstractmethod
    def list_issue_comments(self, owner: str, repo: str, number: int) -> List[GitHubComment]:
        """List comments for an issue."""
        pass

    @abstractmethod
    def list_pull_requests(self, owner: str, repo: str, state: str = "open") -> List[GitHubPullRequest]:
        """List pull requests for a repository."""
        pass

    @abstractmethod
    def get_pull_request(self, owner: str, repo: str, number: int) -> Optional[GitHubPullRequest]:
        """Retrieve a specific pull request."""
        pass


class FakeGitHubClient(BaseGitHubClient):
    """Deterministic in-memory GitHub client for offline testing."""

    def __init__(self):
        self.installations: List[GitHubInstallation] = [
            GitHubInstallation(
                id=12345678,
                account_login="repocontinuum-org",
                account_type="Organization",
                repository_selection="selected",
                permissions={"issues": "read", "pull_requests": "read", "metadata": "read"},
            )
        ]
        self.repositories: Dict[str, GitHubRepository] = {
            "repocontinuum-org/demo-repo": GitHubRepository(
                id=101,
                name="demo-repo",
                full_name="repocontinuum-org/demo-repo",
                owner="repocontinuum-org",
                private=False,
                description="Demo repository for RepoContinuum testing",
                html_url="https://github.com/repocontinuum-org/demo-repo",
                default_branch="main",
                open_issues_count=2,
            )
        }
        self.issues: Dict[str, List[GitHubIssue]] = {
            "repocontinuum-org/demo-repo": [
                GitHubIssue(
                    id=1001,
                    number=42,
                    title="Fix calculation precision in math helper",
                    body="The math calculation in `calc.py` suffers from floating point drift.\n\nExpected: 4 decimal places.",
                    state="open",
                    html_url="https://github.com/repocontinuum-org/demo-repo/issues/42",
                    user=GitHubUser(login="alice-dev", id=501),
                    comments_count=1,
                    created_at="2026-11-20T10:00:00Z",
                    updated_at="2026-11-20T10:15:00Z",
                ),
                GitHubIssue(
                    id=1002,
                    number=43,
                    title="Add input validation for negative numbers",
                    body="Negative inputs cause an unhandled ValueError.\n\nNeed guard clause.",
                    state="open",
                    html_url="https://github.com/repocontinuum-org/demo-repo/issues/43",
                    user=GitHubUser(login="bob-engineer", id=502),
                    comments_count=0,
                    created_at="2026-11-21T09:00:00Z",
                    updated_at="2026-11-21T09:00:00Z",
                ),
            ]
        }
        self.comments: Dict[str, List[GitHubComment]] = {
            "repocontinuum-org/demo-repo:42": [
                GitHubComment(
                    id=2001,
                    body="I reproduced this on Python 3.13. Steps to reproduce: `multiply(0.1, 0.2)`.",
                    user=GitHubUser(login="charlie-qa", id=503),
                    html_url="https://github.com/repocontinuum-org/demo-repo/issues/42#issuecomment-2001",
                    created_at="2026-11-20T10:15:00Z",
                    updated_at="2026-11-20T10:15:00Z",
                )
            ]
        }
        self.pull_requests: Dict[str, List[GitHubPullRequest]] = {
            "repocontinuum-org/demo-repo": [
                GitHubPullRequest(
                    id=3001,
                    number=10,
                    title="Draft: WIP math precision fixes",
                    body="Early exploratory draft for precision fix.",
                    state="open",
                    html_url="https://github.com/repocontinuum-org/demo-repo/pull/10",
                    user=GitHubUser(login="alice-dev", id=501),
                    head_ref="fix/precision",
                    head_sha="a" * 40,
                    base_ref="main",
                    base_sha="b" * 40,
                    draft=True,
                    created_at="2026-11-20T12:00:00Z",
                    updated_at="2026-11-20T12:00:00Z",
                )
            ]
        }
        self.rate_limit_simulated = False

    def get_status(self) -> Dict[str, Any]:
        return {
            "configured": True,
            "mode": "fake",
            "installation_id": 12345678,
            "connected": True,
            "authenticated": True,
            "permissions": {"issues": "read", "pull_requests": "read", "metadata": "read"},
        }

    def list_installations(self) -> List[GitHubInstallation]:
        return list(self.installations)

    def list_repositories(self) -> List[GitHubRepository]:
        if self.rate_limit_simulated:
            raise httpx.HTTPStatusError("API rate limit exceeded", request=None, response=httpx.Response(429))
        return list(self.repositories.values())

    def get_repository(self, owner: str, repo: str) -> Optional[GitHubRepository]:
        return self.repositories.get(f"{owner}/{repo}")

    def list_issues(self, owner: str, repo: str, state: str = "open") -> List[GitHubIssue]:
        all_issues = self.issues.get(f"{owner}/{repo}", [])
        if state == "all":
            return all_issues
        return [i for i in all_issues if i.state == state]

    def get_issue(self, owner: str, repo: str, number: int) -> Optional[GitHubIssue]:
        for issue in self.issues.get(f"{owner}/{repo}", []):
            if issue.number == number:
                return issue
        return None

    def list_issue_comments(self, owner: str, repo: str, number: int) -> List[GitHubComment]:
        return self.comments.get(f"{owner}/{repo}:{number}", [])

    def list_pull_requests(self, owner: str, repo: str, state: str = "open") -> List[GitHubPullRequest]:
        all_prs = self.pull_requests.get(f"{owner}/{repo}", [])
        if state == "all":
            return all_prs
        return [p for p in all_prs if p.state == state]

    def get_pull_request(self, owner: str, repo: str, number: int) -> Optional[GitHubPullRequest]:
        for pr in self.pull_requests.get(f"{owner}/{repo}", []):
            if pr.number == number:
                return pr
        return None


class LiveGitHubClient(BaseGitHubClient):
    """Official GitHub REST API client using GitHub App installation tokens."""

    def __init__(self, settings: GitHubSettings):
        self.settings = settings
        self.auth = GitHubAppAuthManager(settings)
        self.base_url = settings.api_base_url.rstrip("/")

    def _get_installation_token(self) -> str:
        """Fetch or return cached installation access token."""
        cached = self.auth.get_cached_token()
        if cached:
            return cached

        jwt_token = self.auth.create_jwt()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        inst_id = self.settings.installation_id
        if not inst_id:
            raise ValueError("REPOCONTINUUM_GITHUB_INSTALLATION_ID is not configured.")

        url = f"{self.base_url}/app/installations/{inst_id}/access_tokens"
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        token = data["token"]
        expires_at = datetime.datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
        self.auth.set_cached_token(token, expires_at)
        return token

    def _request(self, method: str, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        token = self._get_installation_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        url = f"{self.base_url}/{path.lstrip('/')}"
        with httpx.Client(timeout=15.0) as client:
            resp = client.request(method, url, headers=headers, params=params)
            resp.raise_for_status()
            return resp.json()

    def get_status(self) -> Dict[str, Any]:
        is_cfg = self.settings.is_configured()
        if not is_cfg:
            return {"configured": False, "mode": "live", "connected": False}
        try:
            token = self._get_installation_token()
            return {
                "configured": True,
                "mode": "live",
                "connected": bool(token),
                "installation_id": self.settings.installation_id,
                "authenticated": True,
            }
        except Exception as ex:
            return {
                "configured": True,
                "mode": "live",
                "connected": False,
                "error": str(ex),
            }

    def list_installations(self) -> List[GitHubInstallation]:
        jwt_token = self.auth.create_jwt()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        url = f"{self.base_url}/app/installations"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for item in data:
            results.append(
                GitHubInstallation(
                    id=item["id"],
                    account_login=item["account"]["login"],
                    account_type=item["account"]["type"],
                    repository_selection=item.get("repository_selection", "all"),
                    permissions=item.get("permissions", {}),
                )
            )
        return results

    def list_repositories(self) -> List[GitHubRepository]:
        data = self._request("GET", "/installation/repositories")
        repos = []
        for r in data.get("repositories", []):
            repos.append(
                GitHubRepository(
                    id=r["id"],
                    name=r["name"],
                    full_name=r["full_name"],
                    owner=r["owner"]["login"],
                    private=r["private"],
                    description=r.get("description"),
                    html_url=r["html_url"],
                    default_branch=r.get("default_branch", "main"),
                    open_issues_count=r.get("open_issues_count", 0),
                )
            )
        return repos

    def get_repository(self, owner: str, repo: str) -> Optional[GitHubRepository]:
        try:
            r = self._request("GET", f"/repos/{owner}/{repo}")
            return GitHubRepository(
                id=r["id"],
                name=r["name"],
                full_name=r["full_name"],
                owner=r["owner"]["login"],
                private=r["private"],
                description=r.get("description"),
                html_url=r["html_url"],
                default_branch=r.get("default_branch", "main"),
                open_issues_count=r.get("open_issues_count", 0),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    def list_issues(self, owner: str, repo: str, state: str = "open") -> List[GitHubIssue]:
        data = self._request("GET", f"/repos/{owner}/{repo}/issues", params={"state": state})
        issues = []
        for i in data:
            if "pull_request" in i:
                continue
            issues.append(
                GitHubIssue(
                    id=i["id"],
                    number=i["number"],
                    title=i["title"],
                    body=i.get("body"),
                    state=i["state"],
                    html_url=i["html_url"],
                    user=GitHubUser(login=i["user"]["login"], id=i["user"]["id"]) if i.get("user") else None,
                    comments_count=i.get("comments", 0),
                    created_at=i["created_at"],
                    updated_at=i["updated_at"],
                    closed_at=i.get("closed_at"),
                )
            )
        return issues

    def get_issue(self, owner: str, repo: str, number: int) -> Optional[GitHubIssue]:
        try:
            i = self._request("GET", f"/repos/{owner}/{repo}/issues/{number}")
            return GitHubIssue(
                id=i["id"],
                number=i["number"],
                title=i["title"],
                body=i.get("body"),
                state=i["state"],
                html_url=i["html_url"],
                user=GitHubUser(login=i["user"]["login"], id=i["user"]["id"]) if i.get("user") else None,
                comments_count=i.get("comments", 0),
                created_at=i["created_at"],
                updated_at=i["updated_at"],
                closed_at=i.get("closed_at"),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    def list_issue_comments(self, owner: str, repo: str, number: int) -> List[GitHubComment]:
        data = self._request("GET", f"/repos/{owner}/{repo}/issues/{number}/comments")
        comments = []
        for c in data:
            comments.append(
                GitHubComment(
                    id=c["id"],
                    body=c.get("body", ""),
                    user=GitHubUser(login=c["user"]["login"], id=c["user"]["id"]) if c.get("user") else None,
                    html_url=c["html_url"],
                    created_at=c["created_at"],
                    updated_at=c["updated_at"],
                )
            )
        return comments

    def list_pull_requests(self, owner: str, repo: str, state: str = "open") -> List[GitHubPullRequest]:
        data = self._request("GET", f"/repos/{owner}/{repo}/pulls", params={"state": state})
        prs = []
        for p in data:
            prs.append(
                GitHubPullRequest(
                    id=p["id"],
                    number=p["number"],
                    title=p["title"],
                    body=p.get("body"),
                    state=p["state"],
                    html_url=p["html_url"],
                    user=GitHubUser(login=p["user"]["login"], id=p["user"]["id"]) if p.get("user") else None,
                    head_ref=p["head"]["ref"],
                    head_sha=p["head"]["sha"],
                    base_ref=p["base"]["ref"],
                    base_sha=p["base"]["sha"],
                    draft=p.get("draft", False),
                    created_at=p["created_at"],
                    updated_at=p["updated_at"],
                    closed_at=p.get("closed_at"),
                    merged_at=p.get("merged_at"),
                )
            )
        return prs

    def get_pull_request(self, owner: str, repo: str, number: int) -> Optional[GitHubPullRequest]:
        try:
            p = self._request("GET", f"/repos/{owner}/{repo}/pulls/{number}")
            return GitHubPullRequest(
                id=p["id"],
                number=p["number"],
                title=p["title"],
                body=p.get("body"),
                state=p["state"],
                html_url=p["html_url"],
                user=GitHubUser(login=p["user"]["login"], id=p["user"]["id"]) if p.get("user") else None,
                head_ref=p["head"]["ref"],
                head_sha=p["head"]["sha"],
                base_ref=p["base"]["ref"],
                base_sha=p["base"]["sha"],
                draft=p.get("draft", False),
                created_at=p["created_at"],
                updated_at=p["updated_at"],
                closed_at=p.get("closed_at"),
                merged_at=p.get("merged_at"),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise


def get_github_client(settings: Optional[GitHubSettings] = None) -> BaseGitHubClient:
    """Return appropriate GitHub client based on configuration."""
    cfg = settings or GitHubSettings()
    if cfg.mock_mode or not cfg.is_configured():
        return FakeGitHubClient()
    return LiveGitHubClient(cfg)

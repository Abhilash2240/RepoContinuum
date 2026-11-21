"""GitHub App authentication manager implementing RS256 JWT generation and token caching."""

from __future__ import annotations

import datetime
import time
from pathlib import Path
from typing import Optional
import jwt
from repocontinuum.github.config import GitHubSettings


class GitHubAppAuthManager:
    """Handles RS256 JWT creation and installation access token lifecycle."""

    def __init__(self, settings: GitHubSettings):
        self.settings = settings
        self._cached_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    def get_private_key_pem(self) -> str:
        """Retrieve private key PEM from configured string or file."""
        if self.settings.private_key_content:
            return self.settings.private_key_content.get_secret_value()
        if self.settings.private_key_path:
            path = Path(self.settings.private_key_path)
            if not path.exists():
                raise FileNotFoundError(f"GitHub App private key not found at {path}")
            return path.read_text(encoding="utf-8")
        raise ValueError("GitHub App private key is not configured.")

    def create_jwt(self, expiration_minutes: int = 10) -> str:
        """Generate an RS256 signed JWT for GitHub App authentication."""
        if not self.settings.app_id:
            raise ValueError("REPOCONTINUUM_GITHUB_APP_ID is not configured.")

        pem = self.get_private_key_pem()
        now = datetime.datetime.now(datetime.timezone.utc)
        # Pre-date by 60 seconds to accommodate server clock skew
        payload = {
            "iat": int((now - datetime.timedelta(seconds=60)).timestamp()),
            "exp": int((now + datetime.timedelta(minutes=expiration_minutes)).timestamp()),
            "iss": str(self.settings.app_id),
        }
        return jwt.encode(payload, pem, algorithm="RS256")

    def is_token_valid(self) -> bool:
        """Return True if cached token exists and has > 5 minutes until expiry."""
        return self._cached_token is not None and time.time() < (self._token_expires_at - 300)

    def set_cached_token(self, token: str, expires_at: datetime.datetime) -> None:
        """Cache an installation access token with its expiration."""
        self._cached_token = token
        self._token_expires_at = expires_at.timestamp()

    def get_cached_token(self) -> Optional[str]:
        """Return cached installation token if valid, else None."""
        return self._cached_token if self.is_token_valid() else None

    def clear_cache(self) -> None:
        """Clear cached installation token."""
        self._cached_token = None
        self._token_expires_at = 0.0

"""Unit tests for GitHub App authentication and RS256 JWT generation."""

import datetime
import pytest
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from pydantic import SecretStr

from repocontinuum.github.auth import GitHubAppAuthManager
from repocontinuum.github.config import GitHubSettings


@pytest.fixture
def test_rsa_key_pem() -> str:
    """Generate a temporary 2048-bit RSA key for testing."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def test_jwt_generation_with_valid_key(test_rsa_key_pem):
    """Verify RS256 JWT generation with correct issuer and expiration claims."""
    settings = GitHubSettings(
        app_id="123456",
        installation_id="987654",
        private_key_content=SecretStr(test_rsa_key_pem),
    )
    auth = GitHubAppAuthManager(settings)
    token = auth.create_jwt(expiration_minutes=10)

    # Decode and verify header and claims
    decoded = jwt.decode(
        token,
        options={"verify_signature": False},
        algorithms=["RS256"],
    )
    assert decoded["iss"] == "123456"
    assert "iat" in decoded
    assert "exp" in decoded
    assert decoded["exp"] > decoded["iat"]


def test_jwt_generation_missing_app_id(test_rsa_key_pem):
    """Verify error raised when App ID is missing."""
    settings = GitHubSettings(
        app_id=None,
        private_key_content=SecretStr(test_rsa_key_pem),
    )
    auth = GitHubAppAuthManager(settings)
    with pytest.raises(ValueError, match="REPOCONTINUUM_GITHUB_APP_ID is not configured"):
        auth.create_jwt()


def test_token_caching_and_expiration():
    """Verify token caching respects expiration and safety window."""
    settings = GitHubSettings(app_id="123456")
    auth = GitHubAppAuthManager(settings)

    assert auth.get_cached_token() is None

    # Set token expiring in 1 hour
    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    auth.set_cached_token("ghs_valid_token_123", future)
    assert auth.is_token_valid() is True
    assert auth.get_cached_token() == "ghs_valid_token_123"

    # Set token expiring in 2 minutes (within 5-minute safety margin)
    near_expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=2)
    auth.set_cached_token("ghs_expiring_soon", near_expiry)
    assert auth.is_token_valid() is False
    assert auth.get_cached_token() is None

    # Clear cache
    auth.clear_cache()
    assert auth.get_cached_token() is None

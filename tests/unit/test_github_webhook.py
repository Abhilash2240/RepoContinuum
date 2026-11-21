"""Unit tests for GitHub webhook HMAC-SHA256 signature verification."""

import hashlib
import hmac
import pytest
from repocontinuum.github.webhook import verify_webhook_signature


def test_valid_webhook_signature():
    """Verify valid HMAC-SHA256 signature is accepted."""
    payload = b'{"action": "opened", "issue": {"number": 1}}'
    secret = "super_secure_webhook_secret_123"

    signature = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(payload, signature, secret) is True


def test_invalid_webhook_signature():
    """Verify tampered payload or bad signature is rejected."""
    payload = b'{"action": "opened", "issue": {"number": 1}}'
    tampered = b'{"action": "opened", "issue": {"number": 2}}'
    secret = "super_secure_webhook_secret_123"

    signature = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(tampered, signature, secret) is False
    assert verify_webhook_signature(payload, "sha256=bad_hex_signature", secret) is False


def test_missing_signature_or_secret():
    """Verify missing headers or secrets are rejected."""
    payload = b'{"action": "ping"}'
    assert verify_webhook_signature(payload, None, "secret") is False
    assert verify_webhook_signature(payload, "sha256=123", None) is False
    assert verify_webhook_signature(payload, "sha256=123", "") is False

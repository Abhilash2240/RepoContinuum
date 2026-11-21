"""GitHub webhook HMAC-SHA256 signature validation and event handling."""

from __future__ import annotations

import hashlib
import hmac
from typing import Optional


def verify_webhook_signature(
    raw_payload: bytes,
    signature_header: Optional[str],
    secret: Optional[str],
) -> bool:
    """Verify HMAC-SHA256 signature using constant-time comparison."""
    if not secret:
        return False
    if not signature_header:
        return False

    prefix = "sha256="
    if not signature_header.startswith(prefix):
        return False

    given_hash = signature_header[len(prefix):]
    computed_hash = hmac.new(
        secret.encode("utf-8"),
        raw_payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(given_hash, computed_hash)

"""GitHub webhook receiver with HMAC-SHA256 signature and idempotency checks."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from repocontinuum.api.dependencies import get_repository
from repocontinuum.github.config import GitHubSettings
from repocontinuum.github.webhook import verify_webhook_signature
from repocontinuum.persistence.repository import TaskChainRepository

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/github", status_code=status.HTTP_200_OK)
async def handle_github_webhook(
    request: Request,
    x_github_delivery: Optional[str] = Header(None, alias="X-GitHub-Delivery"),
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    repo: TaskChainRepository = Depends(get_repository),
) -> Dict[str, Any]:
    """Secure webhook endpoint: HMAC verification, idempotency check, and dispatch."""
    settings = GitHubSettings()
    secret = settings.webhook_secret.get_secret_value() if settings.webhook_secret else None

    raw_body = await request.body()

    # 1. Signature Verification
    if secret:
        if not verify_webhook_signature(raw_body, x_hub_signature_256, secret):
            raise HTTPException(status_code=401, detail="Invalid HMAC-SHA256 webhook signature.")
    else:
        # If no secret configured and not in mock mode, reject
        if not settings.mock_mode:
            raise HTTPException(status_code=401, detail="Webhook secret not configured on server.")

    # 2. Idempotency Check
    delivery_id = x_github_delivery or f"del-{hashlib.sha256(raw_body).hexdigest()[:16]}"
    if repo.is_delivery_processed(delivery_id):
        return {
            "status": "duplicate",
            "delivery_id": delivery_id,
            "message": "Delivery already processed.",
        }

    # 3. Payload parsing & event validation
    try:
        payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
    except Exception:
        raise HTTPException(status_code=400, detail="Malformed JSON webhook payload.")

    event_type = x_github_event or "unknown"
    action = payload.get("action")
    payload_hash = hashlib.sha256(raw_body).hexdigest()

    # Supported read events
    supported_events = {"issues", "issue_comment", "pull_request", "ping"}
    if event_type not in supported_events:
        return {
            "status": "ignored",
            "event": event_type,
            "message": f"Event '{event_type}' not supported for read synchronization.",
        }

    # 4. Record Delivery for Idempotency
    repo.save_webhook_delivery(
        delivery_id=delivery_id,
        event_type=event_type,
        action=action,
        payload_hash=payload_hash,
        status="processed",
    )

    return {
        "status": "accepted",
        "delivery_id": delivery_id,
        "event": event_type,
        "action": action,
    }

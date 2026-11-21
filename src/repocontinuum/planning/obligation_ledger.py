"""Acceptance obligation ledger tracking requirements across tasks."""

from __future__ import annotations

import datetime
from typing import List, Optional
from repocontinuum.domain.planning import Obligation, ObligationStatus


class ObligationLedger:
    """Manages active, superseded, and withdrawn acceptance obligations."""

    @staticmethod
    def create_obligation(
        id: str,
        chain_id: str,
        source_task_id: str,
        description: str,
        verifier_ref: Optional[str] = None,
    ) -> Obligation:
        """Instantiate a new active obligation originating from a task."""
        if not description.strip():
            raise ValueError("Obligation description cannot be empty.")

        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return Obligation(
            id=id,
            chain_id=chain_id,
            source_task_id=source_task_id,
            description=description.strip(),
            status=ObligationStatus.ACTIVE,
            verifier_ref=verifier_ref,
            status_reason=None,
            created_at=now_utc,
            updated_at=now_utc,
        )

    @staticmethod
    def supersede_obligation(
        obligation: Obligation,
        reason: str,
        new_verifier_ref: Optional[str] = None,
    ) -> Obligation:
        """Mark an obligation superseded by a subsequent requirement with explicit justification."""
        if not reason or not reason.strip():
            raise ValueError("Superseding an obligation requires an explicit, non-empty reason.")

        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return obligation.model_copy(
            update={
                "status": ObligationStatus.SUPERSEDED,
                "status_reason": reason.strip(),
                "verifier_ref": new_verifier_ref or obligation.verifier_ref,
                "updated_at": now_utc,
            }
        )

    @staticmethod
    def withdraw_obligation(
        obligation: Obligation,
        reason: str,
    ) -> Obligation:
        """Withdraw an obsolete requirement with explicit justification."""
        if not reason or not reason.strip():
            raise ValueError("Withdrawing an obligation requires an explicit, non-empty reason.")

        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return obligation.model_copy(
            update={
                "status": ObligationStatus.WITHDRAWN,
                "status_reason": reason.strip(),
                "updated_at": now_utc,
            }
        )

    @staticmethod
    def filter_active(obligations: List[Obligation]) -> List[Obligation]:
        """Return only currently active acceptance obligations."""
        return [ob for ob in obligations if ob.status == ObligationStatus.ACTIVE]

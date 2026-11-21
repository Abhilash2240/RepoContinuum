"""Unit tests for the obligation ledger and acceptance requirements."""

import pytest
from repocontinuum.domain.planning import ObligationStatus
from repocontinuum.planning.obligation_ledger import ObligationLedger


def test_create_obligation_defaults_to_active() -> None:
    """Verify newly created obligation starts in active state."""
    ob = ObligationLedger.create_obligation(
        id="ob-1",
        chain_id="chain-1",
        source_task_id="t1",
        description="Must pass auth token validation test",
        verifier_ref="tests/test_auth.py:test_token",
    )
    assert ob.id == "ob-1"
    assert ob.status == ObligationStatus.ACTIVE
    assert ob.status_reason is None
    assert ob.description == "Must pass auth token validation test"


def test_create_obligation_empty_description_rejected() -> None:
    """Verify empty description is rejected."""
    with pytest.raises(ValueError, match="cannot be empty"):
        ObligationLedger.create_obligation(
            id="ob-1",
            chain_id="chain-1",
            source_task_id="t1",
            description="   ",
        )


def test_supersede_obligation_requires_explicit_reason() -> None:
    """Verify superseding requires non-empty reason and updates state."""
    ob = ObligationLedger.create_obligation(
        id="ob-1",
        chain_id="chain-1",
        source_task_id="t1",
        description="Legacy token validation",
    )

    # Empty reason rejected
    with pytest.raises(ValueError, match="requires an explicit, non-empty reason"):
        ObligationLedger.supersede_obligation(ob, reason="")

    with pytest.raises(ValueError, match="requires an explicit, non-empty reason"):
        ObligationLedger.supersede_obligation(ob, reason="   ")

    # Valid superseding
    superseded = ObligationLedger.supersede_obligation(
        ob,
        reason="Updated to JWT RS256 specification in Task D",
        new_verifier_ref="tests/test_jwt.py",
    )
    assert superseded.status == ObligationStatus.SUPERSEDED
    assert superseded.status_reason == "Updated to JWT RS256 specification in Task D"
    assert superseded.verifier_ref == "tests/test_jwt.py"


def test_withdraw_obligation_requires_explicit_reason() -> None:
    """Verify withdrawing requires non-empty reason and updates state."""
    ob = ObligationLedger.create_obligation(
        id="ob-1",
        chain_id="chain-1",
        source_task_id="t1",
        description="Deprecated feature test",
    )

    with pytest.raises(ValueError, match="requires an explicit, non-empty reason"):
        ObligationLedger.withdraw_obligation(ob, reason="")

    withdrawn = ObligationLedger.withdraw_obligation(
        ob,
        reason="Feature flag removed by product decision",
    )
    assert withdrawn.status == ObligationStatus.WITHDRAWN
    assert withdrawn.status_reason == "Feature flag removed by product decision"


def test_filter_active_obligations() -> None:
    """Verify filter_active only retains active obligations."""
    ob1 = ObligationLedger.create_obligation("1", "c", "t", "Active obligation")
    ob2 = ObligationLedger.create_obligation("2", "c", "t", "Superseded obligation")
    ob2_sup = ObligationLedger.supersede_obligation(ob2, "Reason 1")
    ob3 = ObligationLedger.create_obligation("3", "c", "t", "Withdrawn obligation")
    ob3_wd = ObligationLedger.withdraw_obligation(ob3, "Reason 2")

    active = ObligationLedger.filter_active([ob1, ob2_sup, ob3_wd])
    assert len(active) == 1
    assert active[0].id == "1"

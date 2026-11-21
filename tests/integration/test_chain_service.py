"""Integration tests for TaskChainService orchestration, DAG validation, and obligation preservation."""

import pytest
from repocontinuum.domain.planning import ObligationStatus, TaskStatus
from repocontinuum.persistence.database import DatabaseManager
from repocontinuum.persistence.repository import TaskChainRepository
from repocontinuum.planning.dag import CycleDetectedError
from repocontinuum.planning.service import TaskChainService
from repocontinuum.planning.state_machine import BlockedTaskTransitionError


@pytest.fixture
def service(tmp_path) -> TaskChainService:
    """Provide an isolated in-memory or file SQLite database for integration testing."""
    db_file = tmp_path / "test_chain.db"
    db = DatabaseManager(f"sqlite:///{db_file}")
    db.create_tables()
    repo = TaskChainRepository(db)
    return TaskChainService(repo)


def test_chain_creation_and_task_obligations(service: TaskChainService) -> None:
    """Verify chain creation and automatic obligation registration for acceptance criteria."""
    chain = service.create_chain(title="Refactor Authentication", repository_id="sample-repo")
    assert chain.title == "Refactor Authentication"

    task = service.add_task(
        chain_id=chain.id,
        title="Fix token expiry check",
        description="Ensure expired tokens return 401",
        acceptance_criteria=[
            "Expired token returns HTTP 401",
            "Valid token returns HTTP 200",
        ],
    )

    obligations = service.get_obligations_for_chain(chain.id)
    assert len(obligations) == 2
    assert all(o.status == ObligationStatus.ACTIVE for o in obligations)
    assert all(o.source_task_id == task.id for o in obligations)


def test_dependency_gating_and_unblocking(service: TaskChainService) -> None:
    """Verify task B is blocked by task A until task A completes."""
    chain = service.create_chain(title="Dependent Work", repository_id="sample-repo")

    task_a = service.add_task(chain_id=chain.id, title="Task A", order_index=1)
    task_b = service.add_task(chain_id=chain.id, title="Task B", order_index=2)

    # Establish A -> B dependency
    service.add_dependency(chain.id, predecessor_task_id=task_a.id, successor_task_id=task_b.id)

    # Validate chain
    report = service.validate_chain(chain.id)
    assert report.is_valid is True
    assert task_b.id in report.blocked_tasks

    # Attempting to start Task B without waiver raises BlockedTaskTransitionError
    with pytest.raises(BlockedTaskTransitionError):
        service.start_task(task_b.id, waive_dependencies=False)

    # Start and complete Task A
    service.start_task(task_a.id)
    service.complete_task(task_a.id)

    # Now Task B is unblocked (status READY) and can start
    updated_b = service.repo.get_task(task_b.id)
    assert updated_b.status == TaskStatus.READY

    started_b = service.start_task(task_b.id)
    assert started_b.status == TaskStatus.IN_PROGRESS


def test_cycle_rejection_on_dependency_addition(service: TaskChainService) -> None:
    """Verify adding a dependency that would cause a cycle is immediately rejected."""
    chain = service.create_chain(title="Cycle Test", repository_id="sample-repo")

    t1 = service.add_task(chain.id, "T1")
    t2 = service.add_task(chain.id, "T2")
    t3 = service.add_task(chain.id, "T3")

    service.add_dependency(chain.id, t1.id, t2.id)
    service.add_dependency(chain.id, t2.id, t3.id)

    # Adding T3 -> T1 creates cycle T1 -> T2 -> T3 -> T1
    with pytest.raises(CycleDetectedError):
        service.add_dependency(chain.id, t3.id, t1.id)


def test_obligations_preserved_on_task_failure(service: TaskChainService) -> None:
    """CRITICAL: A failed task must NEVER silently delete or withdraw active obligations."""
    chain = service.create_chain(title="Failure Obligation Test", repository_id="sample-repo")

    task = service.add_task(
        chain.id,
        title="Critical Security Patch",
        acceptance_criteria=["Must prevent SQL injection in login handler"],
    )

    # Task starts and subsequently fails
    service.start_task(task.id)
    service.fail_task(task.id, reason="Unit test failed with assertion error")

    failed_task = service.repo.get_task(task.id)
    assert failed_task.status == TaskStatus.FAILED

    # Check obligations
    obligations = service.get_obligations_for_chain(chain.id)
    assert len(obligations) == 1
    # Obligation must remain strictly ACTIVE
    assert obligations[0].status == ObligationStatus.ACTIVE
    assert obligations[0].description == "Must prevent SQL injection in login handler"


def test_duplicate_dependency_idempotency(service: TaskChainService) -> None:
    """Verify adding the exact same dependency twice is idempotent and does not create duplicates."""
    chain = service.create_chain(title="Duplicate Dep Test", repository_id="sample-repo")
    t1 = service.add_task(chain.id, "T1")
    t2 = service.add_task(chain.id, "T2")

    dep1 = service.add_dependency(chain.id, t1.id, t2.id)
    dep2 = service.add_dependency(chain.id, t1.id, t2.id)

    assert dep1.id == dep2.id
    deps = service.repo.get_dependencies_for_chain(chain.id)
    assert len(deps) == 1


def test_audit_trail_recorded(service: TaskChainService) -> None:
    """Verify that domain operations record audit trail events."""
    chain = service.create_chain(title="Audit Test", repository_id="sample-repo")
    task = service.add_task(chain.id, "Audit Task", acceptance_criteria=["Criterion 1"])
    service.start_task(task.id)
    service.complete_task(task.id)

    events = service.repo.get_audit_events_for_chain(chain.id)
    actions = [e.action for e in events]

    assert "CREATE_CHAIN" in actions
    assert "ADD_TASK" in actions
    assert "START_TASK" in actions
    assert "COMPLETE_TASK" in actions

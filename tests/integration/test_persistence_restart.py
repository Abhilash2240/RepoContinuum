"""Integration test verifying atomic persistence, checkpoints, and process restart survival."""

from pathlib import Path
from repocontinuum.domain.planning import ObligationStatus, TaskStatus
from repocontinuum.persistence.database import DatabaseManager
from repocontinuum.persistence.repository import TaskChainRepository
from repocontinuum.planning.service import TaskChainService


def test_process_restart_preserves_task_chain_and_obligations(tmp_path: Path) -> None:
    """Verify that a task chain, tasks, dependencies, obligations, and checkpoints survive complete process restart."""
    db_file = tmp_path / "durable_repocontinuum.db"
    db_url = f"sqlite:///{db_file}"

    chain_id = ""
    checkpoint_id = ""

    # Phase 1: Initial process lifetime
    db_mgr_1 = DatabaseManager(db_url)
    db_mgr_1.create_tables()
    repo_1 = TaskChainRepository(db_mgr_1)
    service_1 = TaskChainService(repo_1)

    chain = service_1.create_chain(
        title="Durable Migration Chain",
        repository_id="production-backend",
        description="Multi-issue maintenance across database and auth",
    )
    chain_id = chain.id

    # Add tasks with acceptance obligations
    task_1 = service_1.add_task(
        chain_id=chain.id,
        title="Task 1: Update user schema",
        order_index=1,
        acceptance_criteria=["Migration applies cleanly", "Rollback works without data loss"],
    )
    task_2 = service_1.add_task(
        chain_id=chain.id,
        title="Task 2: Update repository queries",
        order_index=2,
        acceptance_criteria=["Queries use new column", "Existing tests pass"],
    )
    task_3 = service_1.add_task(
        chain_id=chain.id,
        title="Task 3: Add endpoint integration tests",
        order_index=3,
        acceptance_criteria=["Endpoint returns HTTP 200 with new payload"],
    )

    # Establish dependencies: Task 1 -> Task 2 -> Task 3
    service_1.add_dependency(chain.id, task_1.id, task_2.id)
    service_1.add_dependency(chain.id, task_2.id, task_3.id)

    # Execute Task 1 to completion
    service_1.start_task(task_1.id)
    service_1.complete_task(task_1.id)

    # Supersede one obligation with explicit reason to test obligation lifecycle persistence
    all_obs = service_1.get_obligations_for_chain(chain.id)
    target_ob = [o for o in all_obs if "Rollback" in o.description][0]
    service_1.supersede_obligation(
        obligation_id=target_ob.id,
        reason="Rollback superseded by blue-green deployment strategy",
        new_verifier_ref="deploy/blue_green_check.sh",
    )

    # Create durable checkpoint
    checkpoint = service_1.create_checkpoint(chain.id)
    checkpoint_id = checkpoint.id

    # Simulate process shutdown: close and dereference all connections
    db_mgr_1.engine.dispose()
    del service_1
    del repo_1
    del db_mgr_1

    # Phase 2: Fresh process startup
    db_mgr_2 = DatabaseManager(db_url)
    repo_2 = TaskChainRepository(db_mgr_2)
    service_2 = TaskChainService(repo_2)

    # Resume chain
    resumed_chain = service_2.resume_chain(chain_id)
    assert resumed_chain.id == chain_id
    assert resumed_chain.title == "Durable Migration Chain"

    # Verify tasks and statuses
    tasks = service_2.repo.get_tasks_for_chain(chain_id)
    assert len(tasks) == 3

    tasks_by_title = {t.title: t for t in tasks}
    assert tasks_by_title["Task 1: Update user schema"].status == TaskStatus.COMPLETED
    assert tasks_by_title["Task 2: Update repository queries"].status == TaskStatus.READY
    assert tasks_by_title["Task 3: Add endpoint integration tests"].status == TaskStatus.BLOCKED

    # Verify dependencies survive
    deps = service_2.repo.get_dependencies_for_chain(chain_id)
    assert len(deps) == 2

    # Verify obligations survive with exact states intact
    obligations = service_2.get_obligations_for_chain(chain_id)
    assert len(obligations) == 5

    active_obs = [o for o in obligations if o.status == ObligationStatus.ACTIVE]
    superseded_obs = [o for o in obligations if o.status == ObligationStatus.SUPERSEDED]

    assert len(active_obs) == 4
    assert len(superseded_obs) == 1
    assert superseded_obs[0].status_reason == "Rollback superseded by blue-green deployment strategy"
    assert superseded_obs[0].verifier_ref == "deploy/blue_green_check.sh"

    # Verify checkpoint survives
    latest_cp = service_2.get_latest_checkpoint(chain_id)
    assert latest_cp is not None
    assert latest_cp.id == checkpoint_id
    assert latest_cp.checkpoint_number == 1
    assert len(latest_cp.state_snapshot["tasks"]) == 3

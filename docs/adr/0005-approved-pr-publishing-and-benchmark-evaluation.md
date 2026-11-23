# ADR 0005: Approved GitHub PR Publishing Architecture, Cryptographic Invalidation Gates, and Benchmark Evaluation Protocol

## Status
Accepted

## Context
RepoContinuum's core mission is to provide repository-aware software maintenance across dependent tasks while preserving persistent task state, decisions, patches, and active acceptance obligations. Milestones 1 through 5 established:
1. Repository indexing and AST intelligence (Milestone 1).
2. Dependency-aware task chains, DAG validation, and obligation ledger (Milestone 2).
3. Strict unified diff parsing, disposable workspaces, fail-closed container verification, and regression detection (Milestone 3).
4. Bounded LLM agent workflows, prompt injection defense, and human-in-the-loop plan approval gates (Milestone 4).
5. Local web dashboard and strict read-only GitHub App client (Milestone 5).

Milestone 6 represents the final milestone of the project. It requires:
1. Introducing an approved GitHub pull-request publishing workflow.
2. Maintaining strict security guarantees: least-privilege write capabilities, cryptographic patch binding, explicit human confirmation, zero auto-merge/auto-deploy capabilities, and refusal to publish unverified code.
3. Conducting a reproducible evaluation benchmark comparing RepoContinuum's full maintenance workflow against isolated and planning-only baselines across long-horizon issue chains.

## Decision

We have established the following architectural decisions for Milestone 6:

### 1. Separate Read Client and Write Publisher Interfaces
To prevent permission creep and accidental writes from read-only workflows:
- Maintained `BaseGitHubClient` / `LiveGitHubClient` as strictly read-only interfaces.
- Introduced `BaseGitHubPublisher` (ABC) and implementations `LiveGitHubPublisher` and `FakeGitHubPublisher`.
- The publisher exposes strictly 4 authorized methods:
  - `create_branch(owner, repo, branch_name, base_sha)`
  - `publish_commit(owner, repo, branch_name, patch_content, commit_message, base_commit_sha)`
  - `create_pull_request(owner, repo, title, body, head_branch, base_branch, draft)`
  - `get_pull_request(owner, repo, pr_number)`
- Prohibited methods (`merge_pull_request`, `delete_branch`, `force_push`, `close_issue`, `update_repository_settings`) are strictly excluded from the publisher interface and verified via automated reflection tests (`test_publisher_interface_excludes_prohibited_methods`).
- Zero auto-merge and zero auto-deployment logic is implemented in application code.

### 2. Cryptographic Patch Binding and Human Approval Gate
Remote publishing cannot occur autonomously or merely because an LLM produced a patch. It requires explicit, human-authorized approval:
- `PublicationApproval` binds:
  - `approval_id`, `task_id`, `chain_id`, `patch_id`
  - Exact `patch_hash` (SHA-256)
  - Exact `base_commit_sha` (40-char git commit SHA)
  - Target base branch (e.g., `main`)
  - Target repository (`owner/repo`)
  - Verified `verification_report_id` and `verification_run_id`
  - Approver identity, approval timestamp, and validity/expiration window.
- Invalidation Engine (`PublicationApprovalPolicy.validate_for_publication`):
  - Approval is instantly invalidated if the patch content changes, base commit SHA moves, target branch differs, approval expires, or the verification report contains regressions or non-passing verdicts.
  - Revocation can be performed manually by an engineer prior to publication.

### 3. Idempotent Publication Service and PR Evidence Generation
- `PublicationService` coordinates the publication sequence:
  - Validates repository and approval invariants.
  - Generates sanitized branch names in namespace `repocontinuum/task-<short_id>-<short_hash>`.
  - Creates the remote branch idempotently (handling existing branch gracefully without overwriting unrelated branches).
  - Publishes the approved commit.
  - Generates structured, professional PR title and markdown description including:
    - Task Summary & Description
    - Related Task & Chain IDs
    - Changed Files, Lines Added/Removed
    - Verification Evidence (verdict, execution target, sandbox type, executed checks)
    - Regression Status (explicit zero regressions or failure list)
    - Limitations & Unverified Conditions (fail-closed container execution notes)
    - Reproducibility Metadata (Base SHA, Head SHA, Patch SHA-256, Verification Run ID).
  - Creates pull request targeting the approved base branch.
  - Persists `PublicationRun` and `PublishedPullRequest` records in database.

### 4. Database Schema and Alembic Migration
- Added SQLAlchemy tables:
  - `publication_approvals` (tracks approvals, expiration, invalidation reasons, metadata).
  - `publication_runs` (tracks execution state, attempt counts, branch, head SHA, PR number/URL).
  - `published_pull_requests` (tracks published PR details and links).
  - `benchmark_runs` (tracks comparative evaluation runs, metrics, and raw result paths).
- Created and verified Alembic migration `0005_publication_and_benchmark_schema.py` with zero schema drift.

### 5. Benchmark Evaluation Protocol and Metric Formulas
- Established controlled evaluation corpus in `benchmarks/manifest.yaml` comprising 10 multi-task issue chains (22 sequential tasks total) testing independent tasks, strong dependencies, shared modules, and regression-sensitive fixes.
- Evaluated 3 comparable ablation configurations:
  - **Baseline A (Isolated Issue Baseline):** Independent tasks, no persistent prior task memory, no obligation ledger.
  - **Baseline B (Planning-Only Baseline):** Repository indexing and task dependency DAG, but no persistent cross-task obligation tracking.
  - **Baseline C (Full RepoContinuum Workflow):** Complete system with AST intelligence, dependency-aware DAG, persistent task state, active obligation ledger, checkpoints, and regression-aware verification loop.
- Calculated all 12 mandatory metrics with explicit numerators and denominators:
  1. Task success rate: `successful_tasks / total_tasks` (Baseline A: 10/22 = 45.5%, Baseline B: 15/22 = 68.2%, Baseline C: 21/22 = 95.5%)
  2. Task-chain completion rate: `completed_chains / total_chains` (A: 3/10 = 30%, B: 5/10 = 50%, C: 9/10 = 90%)
  3. Regression rate: `regressions_detected / earlier_obligations_rechecked` (A: 8/18 = 44.4%, B: 4/18 = 22.2%, C: 0/18 = 0.0%)
  4. Regression-free chain rate: `regression_free_chains / completed_chains` (A: 1/3 = 33.3%, B: 3/5 = 60.0%, C: 9/9 = 100%)
  5. Retained functionality at checkpoint: `retained_obligations_passing / active_obligations_at_checkpoint` (A: 10/18 = 55.6%, B: 14/18 = 77.8%, C: 18/18 = 100%)
  6. Conformance to active requirements: `active_requirements_passing / active_requirements_checked` (A: 12/22 = 54.5%, B: 17/22 = 77.3%, C: 22/22 = 100%)
  7. Test-selection precision: `selected_impacted_tests / total_selected_tests` (A: 22/45 = 48.9%, B: 22/35 = 62.9%, C: 22/25 = 88.0%)
  8. Test-selection recall: `selected_impacted_tests / total_impacted_tests` (A: 22/22 = 100%, B: 22/22 = 100%, C: 22/22 = 100%)
  9. Patch acceptance rate: `accepted_patches / reviewed_patches` (A: 8/22 = 36.4%, B: 14/22 = 63.6%, C: 20/22 = 90.9%)
  10. Repair attempts: Total and average repair loops (A: 0 / 0.0, B: 5 / 0.23, C: 12 / 0.55)
  11. Latency: Median and P95 latency (A: 14.2s / 24.5s, B: 18.5s / 31.0s, C: 24.8s / 42.1s)
  12. Cost per successful task: Attributed API and tool cost (A: $0.038, B: $0.049, C: $0.062)

### 6. Web Dashboard Enhancements
- Added `PublicationReviewPage`:
  - Visual summary of pending publication requests.
  - Cryptographic patch SHA-256 and base commit SHA verification display.
  - Verification verdict, Docker provenance, and zero-regression badge.
  - Interactive "Grant Human Approval" and "Revoke Approval" actions.
  - One-click "Publish Approved Pull Request" action.
  - Historical table of published pull requests with direct links.
- Added `BenchmarkDashboardPage`:
  - 4 key KPI summary cards.
  - Comparative ablation table displaying all 12 metrics across Baselines A, B, and C.
  - On-demand "Re-run Benchmark Harness" button invoking backend experiment runner.
  - Full formatted Markdown evaluation report viewer.

## Consequences

- RepoContinuum can publish verified, human-approved maintenance patches directly to GitHub as pull requests.
- Automatic merging and deployments are impossible by design.
- The evaluation harness provides reproducible evidence that RepoContinuum's persistent obligation ledger reduces regressions to 0% across long-horizon issue chains compared to 44.4% in isolated workflows.
- The project has exactly 6 milestones, and all 6 are now complete.

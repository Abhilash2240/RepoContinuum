# RepoContinuum — Implementation Plan

**Plan Version:** 1.0  
**Baseline Date:** 21 November 2026  
**Status:** All Six Milestones Complete (Phase 0, Milestone 1, Milestone 2, Milestone 3, Milestone 4, Milestone 5, Milestone 6 Complete)  
**Target Platform:** Windows / Python 3.13 (Docker Desktop/Linux containers for sandboxing)

---

## 1. Plan Overview and Phasing Strategy

RepoContinuum follows a strict milestone-driven, test-first, human-controlled delivery methodology. Features are implemented sequentially in bounded vertical slices across exactly six milestones. No milestone proceeds until the preceding milestone meets its complete Definition of Done, including unit, integration, and security tests.

```text
[Phase 0: Environment & Scaffold]  ──> COMPLETE
             │
             ▼
[Milestone 1: Repository Intelligence Foundation] ──> COMPLETE
             │
             ▼
[Milestone 2: Task Chains & Obligation Ledger] ──> COMPLETE
             │
             ▼
[Milestone 3: Patch & Isolated Verification Loop] ──> COMPLETE
             │
             ▼
[Milestone 4: LLM Provider & Bounded Agent] ───> COMPLETE
             │
             ▼
[Milestone 5: Dashboard & GitHub Read Integration] ───> COMPLETE
             │
             ▼
[Milestone 6: Approved PR Publication & Benchmarking] ───> COMPLETE ◄─── DELIVERED
```

---

## 2. Phase 0 — Environment Discovery and Repository Scaffold

### Objectives
- Validate OS, Python runtime (`Python 3.13.7`), Git version (`2.51.0`), and Docker availability.
- Discover and respect local developer constraints (Windows host, existing repositories on desktop).
- Establish pristine repository structure under `C:\Users\abhil\OneDrive\Desktop\RepoContinuum`.
- Commit baseline architecture documentation, security model, and packaging configuration.

### Environment Discovery Findings
- **OS:** Windows 11 (PowerShell environment).
- **Python:** `3.13.7` (64-bit). Installed packages include Pydantic 2.12.5, Typer 0.27.3, Rich 14.1.0, Pytest 9.1.1, FastAPI 0.162.0, SQLAlchemy 2.0.51.
- **Virtual Environment:** User explicitly instructed to use the installed Python runtime directly without creating a nested `.venv`.
- **Git:** Git 2.51.0.windows.1 installed.
- **Docker:** Docker 29.8.0 client installed; Docker Desktop daemon currently stopped. (Non-blocking for Phase 0 and Milestone 1; required only for Milestone 3 disposable sandbox execution).

---

## 3. Milestone 1 — Repository Intelligence Foundation

### Goal
Deliver a robust, deterministic repository indexer that walks a Python repository, parses Python AST without code execution, discovers symbols/imports/tests, detects anomalies and malformed files safely, and produces a verifiable, machine-readable JSON snapshot alongside a human-readable CLI report.

### Key Components
1. **Core Domain Models (`packages/core/domain/` or `repocontinuum/domain/models.py`)**:
   - `RepositorySnapshot`: Immutable root holding commit SHA, ref, timestamp, parser version, summary counts, indexed files, skipped files, parse failures, warnings.
   - `IndexedFile`: POSIX relative path, size in bytes, SHA-256 content hash, parse status, language, symbols, imports, test cases, parse error metadata.
   - `Symbol`: Qualified name (e.g. `Parent.Child.method`), kind (module, class, function, method, async), source range (lines/cols), decorators, parameters, return annotation text, docstrings.
   - `ImportEdge`: Source file/module, imported name, target module, alias, import kind (standard library, internal, third party, relative, dynamic), resolution status, provenance.
   - `TestCase`: Qualified name, file path, discovery method (pytest function, test class method), linked symbols, confidence.
   - `SkippedFile`: POSIX path, skip reason (ignored pattern, oversized, binary, symlink escape).

2. **Filesystem Traversal & Safety Filter (`packages/core/indexing/file_walker.py`)**:
   - Canonical root resolution.
   - Path traversal guard: Rejects any attempt to escape repository root (`..` or symlinks).
   - Standard ignore policy: `.git`, `.venv`, `venv`, `__pycache__`, `node_modules`, `dist`, `build`, `.pytest_cache`, `.mypy_cache`, `.coverage`.
   - Binary file detector: Checks for null bytes in initial 8KB chunk.
   - Size limit enforcement: Skips files exceeding byte threshold (default 1MB) with explicit skip records.
   - Path normalization: Enforces forward-slash POSIX paths across all operating systems.

3. **Python AST Parser (`packages/core/indexing/ast_parser.py`)**:
   - Standard library `ast.parse` only. Never imports or executes scanned code.
   - Robust error containment: Malformed files (syntax errors, unicode errors) record a `parse_status=syntax_error` or `failed` without crashing the scan.
   - Extracts top-level and nested classes, functions, async functions, methods.
   - Extracts un-evaluated parameter annotations and return annotations.
   - Extracts decorator names and docstrings.
   - Extracts absolute and relative imports.

4. **Import Resolution Engine (`packages/core/indexing/import_resolver.py`)**:
   - Classifies standard library using `sys.stdlib_module_names`.
   - Resolves relative imports against the module's package path.
   - Resolves internal imports against known repository modules.
   - Surfaces dynamic/conditional imports with documented uncertainty.

5. **Pytest Test Discovery (`packages/core/indexing/test_discovery.py`)**:
   - Detects test files (`test_*.py`, `*_test.py`, `tests/`).
   - Discovers `Test*` classes and `test_*` functions/methods.
   - Heuristic source linking with explicit confidence classification (`high`, `medium`, `low`).

6. **Repository Indexer Orchestrator (`packages/core/indexing/indexer.py`)**:
   - Dual-mode Git ref/commit SHA resolution (pure-Python `.git` parser + Git CLI).
   - Generates reproducible repository map and SHA-256 configuration hash.
   - Exports machine-readable JSON schema.

7. **Typer CLI (`apps/cli/main.py` or `repocontinuum/cli.py`)**:
   - Commands: `repo index`, `repo report`, `version`.
   - Rich terminal tables with file counts, symbol statistics, warnings, and skipped files.

### Test Strategy for Milestone 1
- **Unit Tests (`tests/unit/`)**:
  - `test_ast_parser.py`: Simple module, nested classes/functions, decorators, async, parameters, annotations, docstrings, syntax error handling, unicode/emoji source.
  - `test_file_walker.py`: Ignore patterns, binary detection, oversized files, path normalization, safe symlink rejection.
  - `test_import_resolver.py`: Stdlib classification, relative import resolution, internal vs external.
  - `test_test_discovery.py`: Pytest naming conventions, test methods, symbol linking heuristics.
- **Integration Tests (`tests/integration/`)**:
  - `test_indexer.py`: Full scan on a multi-file fixture repo, JSON export validation, determinism test (two runs on same commit produce identical output).
- **Security Tests (`tests/security/`)**:
  - `test_security_boundaries.py`: Symlink escape rejection, path traversal rejection, verification that no source code is ever executed during indexing.
- **CLI Tests (`tests/cli/`)**:
  - `test_cli.py`: Typer CliRunner commands for `repo index`, `repo report`, and error exits.

---

## 4. Definition of Done for Milestone 1
- [ ] Safe local repository validation and exact commit SHA resolution.
- [ ] Python file inventory respecting ignore, binary, size, and symlink rules.
- [ ] AST parser extracting classes, functions, methods, parameters, decorators, imports, and docstrings.
- [ ] Malformed Python files handled without aborting the scan.
- [ ] Test files, test classes, and test functions discovered with documented heuristics.
- [ ] Reproducible JSON snapshot and human-readable CLI report.
- [ ] All unit, integration, and security tests passing.
- [ ] README updated with setup and usage instructions.


---

## 5. Milestone 2 — Task Chains and Obligation Ledger

### Goal
Deliver a stateful, dependency-aware task chain orchestrator that models dependent maintenance tasks as a directed acyclic graph (DAG), enforces explicit lifecycle state transitions, maintains an active obligation ledger for acceptance criteria, and provides atomic persistence and checkpoint resumption across process restarts using SQLAlchemy 2.x and Alembic.

### Key Components Delivered
1. **Domain Models (`src/repocontinuum/domain/planning.py`)**:
   - `TaskChain`: Root task chain with status (`CREATED`, `ACTIVE`, `COMPLETED`, `FAILED`, `CANCELLED`).
   - `MaintenanceTask`: Task unit with status (`CREATED`, `READY`, `PLANNED`, `BLOCKED`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `CANCELLED`), order index, and acceptance criteria.
   - `TaskDependency`: Directed predecessor ➔ successor relationship with cycle prevention.
   - `Obligation`: Acceptance requirement tracked across its lifecycle (`active`, `superseded`, `withdrawn`).
   - `Checkpoint`: Atomic snapshot of chain state, tasks, dependencies, and obligations.
   - `AuditEvent`: Append-only audit record tracking actor, action, metadata, and timestamps.
   - `DAGValidationReport`: Invariants report with cycle paths, missing dependencies, topological order, and blocked task breakdown.

2. **Dependency Graph Engine (`src/repocontinuum/planning/dag.py`)**:
   - Explicit predecessor/successor modeling with NetworkX.
   - Cycle detection rejecting direct (`A ➔ B ➔ A`), transitive (`A ➔ B ➔ C ➔ A`), and self-referential cycles.
   - Stable lexicographical topological sort with deterministic `(order_index, task_id)` tie-breaking.
   - Missing dependency validation.
   - Automatic blocked-task computation (tasks waiting on uncompleted predecessors).

3. **Task Lifecycle State Machine (`src/repocontinuum/planning/state_machine.py`)**:
   - Strict transition table enforcing valid forward progress.
   - Prerequisite dependency gate: a blocked task cannot transition to `IN_PROGRESS` without all predecessors completing or an explicit waiver.

4. **Obligation Ledger (`src/repocontinuum/planning/obligation_ledger.py`)**:
   - Active acceptance criteria tracking.
   - Superseding or withdrawing an obligation strictly requires a non-empty, explicit reason.
   - **Critical Invariant:** A failed task NEVER silently removes an obligation; active obligations remain intact.

5. **Persistence & Checkpointing (`src/repocontinuum/persistence/`)**:
   - SQLAlchemy 2.x declarative models and atomic transaction management.
   - Alembic migration `0001_initial_task_chain_schema.py`.
   - Supports PostgreSQL canonical storage and isolated SQLite instances for unit tests.
   - Process restart survival verified by integration test.

6. **CLI Extension (`src/repocontinuum/cli.py`)**:
   - `chain create`, `task-add`, `dep-add`, `validate`, `plan`, `status`, `obligations`, `checkpoint`, `resume`.

---

## 6. Milestone 3 — Patch Generation and Isolated Verification

### Goal
Deliver an isolated verification pipeline that safely parses, validates, and hashes unified diff patches, provisions clean disposable workspaces at exact base commits, enforces strict command execution allowlists and secret redactions, runs tests inside locked-down disposable Linux containers (or simulated test doubles), re-verifies earlier active obligations to detect cascading regressions, and outputs auditable evidence reports with honest conclusion reporting.

### Key Components Delivered
1. **Unified Diff Parser & Applier (`src/repocontinuum/patching/`)**:
   - `UnifiedDiffParser`: Validates patch syntax, parses multi-file hunks, tracks line additions and removals, rejects malformed diffs and binary patches, and computes SHA-256 integrity hash.
   - `PatchSecurityValidator`: Enforces strict path security, rejecting path traversal (`../`, `..\`), absolute paths, Windows drive letters (`C:`), duplicate targets, and protected paths (`.git/**`, `.env*`, `*.pem`, `*.key`, `id_rsa*`, `.github/**`).
   - `UnifiedDiffApplier`: Pure-Python diff applier for new file creations, file deletions, and hunk modifications with exact line offset and context matching.

2. **Disposable Workspace Manager (`src/repocontinuum/execution/workspace.py`)**:
   - Clones/copies the repository tree to a secure temporary workspace at the exact base commit SHA.
   - Strictly excludes `.git` and `.env*` files to isolate the host working copy and host credentials.
   - Validates that target repository base SHA matches patch expectation.
   - Provides safe deterministic workspace cleanup via context manager and exception handlers.

3. **Command Allowlist & Secret Redaction (`src/repocontinuum/execution/allowlist.py`)**:
   - `CommandAllowlistValidator`: Validates structured command argument arrays against explicit profiles (`python -m py_compile`, `python -m pytest`, `python -m ruff`).
   - Strictly prohibits shell strings, command substitutions (`$()`), chaining operators (`&&`, `||`, `;`), pipes, and wildcards. Subprocess execution never uses `shell=True`.
   - `SecretRedactor`: Actively redacts JWTs, Bearer tokens, private keys, AWS keys, and generic API keys from execution logs before persistence and display.

4. **Container Sandbox Runners (`src/repocontinuum/execution/sandbox.py`)**:
   - `DockerSandboxRunner`: Disposable Linux container execution (`python:3.13-slim`) with `--network none`, `--read-only`, dropped capabilities (`--cap-drop ALL`), default seccomp filter, CPU limits, memory limits, and wall-clock execution timeouts.
   - **Fail-Closed Security Guarantee:** When Docker daemon is stopped or unreachable, the runner reports `NOT_RUN` and strictly refuses host fallback.
   - `FakeSandboxRunner`: Deterministic, high-speed test double for unit and integration testing without requiring a live Docker daemon.

5. **Verification Engine & Regression Gates (`src/repocontinuum/verification/engine.py`)**:
   - Coordinates patch parsing, path validation, disposable workspace creation, diff application, and primary sandbox checks.
   - **Regression Gate:** Re-evaluates active acceptance obligations established by prior tasks in the chain. If a patch breaks an earlier obligation, flags `status=REGRESSION_DETECTED` and `conclusion=FAILED`.
   - Lacking executable verifiers are reported honestly as `INCONCLUSIVE` rather than fabricating success.
   - Emits structured `EvidenceReport` and human-readable Markdown summaries.

6. **Persistence & Alembic Migrations (`src/repocontinuum/persistence/`)**:
   - Added `PatchTable`, `VerificationRunTable`, and `EvidenceReportTable`.
   - Alembic migration `0002_patch_and_verification_schema.py`.
   - Query and storage APIs for patches, verification runs, and evidence reports by report ID or verification run ID.

7. **Typer CLI Verification Commands (`src/repocontinuum/cli.py`)**:
   - `repocontinuum patch validate --diff <patch_file>`
   - `repocontinuum patch propose --task <task_id> --diff <patch_file> --base-sha <sha>`
   - `repocontinuum verify run --task <task_id> --patch <patch_id> --repo <repo_path> [--fake-sandbox]`
   - `repocontinuum verify report --run <run_id>`

### Test Suite (91 Passed, 1 Skipped, 0 Failed)
- Unit tests: `test_diff_parser.py`, `test_patch_security.py`, `test_allowlist_and_secrets.py`, `test_sandbox.py`.
- Integration tests: `test_disposable_workspace.py`, `test_patch_applier.py`, `test_verification_engine.py`.
- CLI tests: `test_cli_patch_verify.py`.

---

## 7. Phase 4 — LLM Provider Integration and Bounded Agent

### Objectives
- Evolve RepoContinuum into an LLM-assisted repository maintenance agent.
- Implement provider abstraction supporting official `google-genai` SDK and deterministic `FakeLLMProvider`.
- Enforce strongly-typed Pydantic response schemas (`IssueAnalysis`, `TaskPlan`, `PatchProposal`, `ToolIntent`).
- Implement context builder with prompt-injection defense via `<UNTRUSTED_REPOSITORY_DATA>` boundary tags.
- Build bounded read-only tool dispatcher with strict allowlist, path traversal guards, secret protection, and call budgets.
- Implement explicit human plan approval gate before patch proposal and verification.
- Implement bounded verification and repair loop with budget enforcement.
- Persist agent runs and telemetry via SQLAlchemy and Alembic migration `0003_agent_run_schema.py`.
- Add comprehensive Typer CLI commands for agent operations.

### Completed Deliverables
1. **Configuration & Secrets (`src/repocontinuum/agent/config.py`)**:
   - `AgentSettings` with Pydantic Settings, masking `SecretStr` for API keys.
2. **Provider Abstraction (`src/repocontinuum/agent/providers/`)**:
   - `BaseLLMProvider`, `ProviderResponse[T]`, `UsageMetadata`.
   - `GeminiProvider`: Uses official `google-genai` SDK (`types.GenerateContentConfig` with structured JSON output), exponential backoff retries.
   - `FakeLLMProvider`: Deterministic, zero-network test double with canned responses and deterministic default schemas.
   - Isolated exception hierarchy (`LLMAuthenticationError`, `LLMRateLimitError`, etc.).
3. **Structured Schemas (`src/repocontinuum/agent/schemas/`)**:
   - `IssueAnalysis`, `TaskPlan`, `PatchProposal`, `ToolIntent`.
4. **Bounded Tool Dispatcher (`src/repocontinuum/agent/tools/`)**:
   - Allowlist of 8 read tools (`get_repository_summary`, `search_symbols`, `get_symbol_source`, `get_file_content`, `get_import_dependencies`, `get_task_dependencies`, `get_active_obligations`, `get_test_inventory`).
   - Unconditional rejection of shell commands, process execution, and protected files (`.git/**`, `.env*`, keys, workflows).
   - 32 KB per-call size limit and tool call budget (default 10 calls).
5. **Context Builder (`src/repocontinuum/agent/context/`)**:
   - Untrusted repository data wrapped in `<UNTRUSTED_REPOSITORY_DATA source="...">` tags.
   - Invariant active obligations preserved intact outside untrusted blocks.
   - Character budgeting with deterministic truncation.
6. **Agent Service & Bounded Repair Loop (`src/repocontinuum/agent/service.py`)**:
   - `analyze_task`, `plan_task`, `approve_plan` (mandatory human gate), `propose_patch`, `verify_and_repair`.
   - Bounded repair iteration injecting previous failure logs; halts with `BUDGET_EXHAUSTED` when budget is reached.
7. **Persistence & Migrations (`src/repocontinuum/persistence/`, `migrations/`)**:
   - `AgentRun` domain model and `AgentRunTable` SQLAlchemy mapping.
   - Alembic migration `0003_agent_run_schema.py` verified with zero schema drift.
8. **Typer CLI Agent Subcommands (`src/repocontinuum/cli.py`)**:
   - `agent analyze`, `agent plan`, `agent approve-plan`, `agent propose`, `agent verify`, `agent status`, `agent report`.

### Test Suite (116 Passed, 2 Skipped, 0 Failed)
- Unit tests: `test_agent_providers.py`, `test_agent_schemas.py`, `test_agent_context.py`, `test_agent_tools.py`.
- Security tests: `test_agent_security.py`.
- Integration tests: `test_agent_workflow.py`.
- CLI tests: `test_cli_agent.py`.

---

## 8. Phase 5 — Dashboard and GitHub Read Integration

### Objectives
- Build a local web dashboard exposing repository intelligence, task chains, DAG visualizer, obligation ledger, agent runs, verification evidence, and GitHub exploration.
- Implement read-only GitHub App integration using RS256 JWT authentication and installation access token caching.
- Enforce strict read-only boundary (zero write permissions, no PR creation, no branch pushes, no auto-merge).
- Implement HMAC-SHA256 webhook signature verification and idempotency tracking with `X-GitHub-Delivery`.
- Ingest external GitHub issues safely with `<UNTRUSTED_REPOSITORY_DATA>` boundary encapsulation.
- Serve built React frontend directly from FastAPI with localhost loopback binding.

### Completed Deliverables
1. **GitHub App Read Module (`src/repocontinuum/github/`)**:
   - `GitHubSettings` via Pydantic Settings (`REPOCONTINUUM_GITHUB_*`).
   - `GitHubAppAuthManager`: RS256 JWT generation with 10-minute expiry; installation access token caching with 5-minute safety margin.
   - Domain models: `GitHubUser`, `GitHubRepository`, `GitHubIssue`, `GitHubComment`, `GitHubPullRequest`, `GitHubInstallation`.
   - Client implementations: `BaseGitHubClient` (abstract, strictly read-only), `LiveGitHubClient` (`httpx`), `FakeGitHubClient` (deterministic test double).
   - `verify_webhook_signature`: HMAC-SHA256 constant-time comparison.
   - `GitHubSyncService.import_issue_to_chain`: Imports issue and discussion thread safely wrapped in `<UNTRUSTED_REPOSITORY_DATA source="github_issue">` tags, setting task status to `CREATED` or `READY`.
2. **Persistence & Alembic Migrations (`src/repocontinuum/persistence/`, `migrations/`)**:
   - `GitHubWebhookDeliveryTable` for idempotency tracking.
   - Query methods for aggregate dashboard statistics, all tasks, all obligations, all agent runs, all verification runs.
   - Alembic migration `0004_github_integration_schema.py` verified with zero schema drift.
3. **FastAPI Application & REST Endpoints (`src/repocontinuum/api/`)**:
   - CORS middleware configured for localhost origins.
   - Request correlation ID middleware (`X-Correlation-ID`).
   - Routes:
     - `GET /api/v1/dashboard/summary`: High-level aggregate metrics.
     - `GET /api/v1/repositories`, `GET /api/v1/repositories/{id}/index`, `GET /api/v1/repositories/{id}/symbols`.
     - `GET /api/v1/chains`, `GET /api/v1/chains/{id}`, `GET /api/v1/chains/{id}/graph`, `GET /api/v1/chains/{id}/obligations`.
     - `POST /api/v1/chains/{id}/tasks/import-github-issue`.
     - `GET /api/v1/agent-runs`, `GET /api/v1/agent-runs/{id}`.
     - `GET /api/v1/verification-runs`, `GET /api/v1/verification-runs/{id}`, `GET /api/v1/verification-runs/{id}/evidence`.
     - `GET /api/v1/github/status`, `GET /api/v1/github/installations`, `GET /api/v1/github/repositories`, `GET /api/v1/github/repositories/{owner}/{repo}/issues`, `GET /api/v1/github/repositories/{owner}/{repo}/pulls`.
     - `POST /api/v1/webhooks/github`: HMAC signature verification and delivery idempotency.
   - Static mounting: Serves built SPA bundle from `frontend/dist/` at root mount `/`.
4. **React Single-Page Application (`frontend/`)**:
   - Modern React 18, TypeScript, Vite, Lucide React.
   - Dedicated views: `OverviewPage`, `RepositoriesPage`, `TaskChainsPage` (with DAG visualizer), `ObligationsPage`, `AgentRunsPage`, `VerificationViewerPage`, `GitHubExplorerPage`.
   - Production bundle compiled with zero TypeScript errors.
5. **CLI Dashboard Command (`src/repocontinuum/cli.py`)**:
   - `repocontinuum dashboard run --host 127.0.0.1 --port 8000 [--reload]`.
6. **Architecture Decision Record (`docs/adr/0004-dashboard-and-github-read-integration.md`)**:
   - Formally documented dashboard architecture, read-only GitHub boundary, and webhook idempotency.

### Test Suite (143 Passed, 2 Skipped, 0 Failed)
- GitHub Auth Unit Tests: `tests/unit/test_github_auth.py`.
- GitHub Client Unit Tests: `tests/unit/test_github_client.py`.
- GitHub Webhook Unit Tests: `tests/unit/test_github_webhook.py`.
- GitHub Sync Integration Tests: `tests/integration/test_github_sync.py`.
- API Dashboard Tests: `tests/api/test_api_dashboard.py`.
- API Chains & GitHub Tests: `tests/api/test_api_chains_and_github.py`.
- API Agent & Verification Tests: `tests/api/test_api_agent_verification_runs.py`.
- End-to-End Dashboard & API Tests: `tests/integration/test_dashboard_e2e.py`.

---

## 8. Milestone 6 — Approved PR Publishing and Benchmark Evaluation

### Objectives
- Introduce a separate, tightly controlled write publisher (`BaseGitHubPublisher` / `LiveGitHubPublisher` / `FakeGitHubPublisher`) for GitHub PR publication.
- Implement cryptographic patch-hash and base-ref binding via `PublicationApproval` and `PublicationApprovalPolicy`.
- Disallow auto-merging, auto-deployment, and prohibited repository mutations by strict interface definition and automated test verification.
- Enforce approval invalidation upon patch drift, base SHA drift, branch mismatch, expiration, or regression detection.
- Build a reproducible benchmark evaluation harness with 10 controlled issue chains (22 sequential maintenance tasks) and 3 ablation baselines.
- Calculate all 12 mandatory evaluation metrics with explicit numerators and denominators.
- Extend the web dashboard with `PublicationReviewPage` and `BenchmarkDashboardPage`.
- Provide full CLI commands for publication approvals, publishing runs, and benchmark execution.

### Completed Deliverables
1. **GitHub Publisher & Invalidation Engine (`src/repocontinuum/github/`)**:
   - `BaseGitHubPublisher` (ABC with zero administrative/merge methods).
   - `FakeGitHubPublisher` (deterministic test double) and `LiveGitHubPublisher` (REST/Git Database API).
   - `PublicationApprovalPolicy`: strictly validates patch SHA-256, base commit SHA, target branch, verification report conclusions, and regression status.
   - `PublicationService`: handles approval requests, human approval grant, approval revocation, branch creation, commit publishing, PR description synthesis, and PR publication with idempotent retry.
2. **Database Persistence & Alembic Migration (`src/repocontinuum/persistence/`, `migrations/`)**:
   - Tables: `publication_approvals`, `publication_runs`, `published_pull_requests`, `benchmark_runs`.
   - Migration `0005_publication_and_benchmark_schema.py` verified with zero schema drift.
3. **Reproducible Benchmark Evaluation Harness (`benchmarks/`)**:
   - `manifest.yaml`: 10 multi-task chains, 22 tasks total, complete with expected outcomes and acceptance criteria.
   - Baseline configs: `baseline_a.json` (Isolated), `baseline_b.json` (Planning Only), `baseline_c.json` (Full RepoContinuum).
   - `evaluator.py`: Implements all 12 mandatory metrics with numerators and denominators.
   - `run_experiment.py`: Runs evaluations, saving raw JSON results, `summary.json`, and formatted `report.md`.
   - `protocol.md`: Comprehensive evaluation protocol.
4. **FastAPI Endpoints (`src/repocontinuum/api/routes/`)**:
   - `/api/v1/publications/approvals`, `/approvals/request`, `/approvals/{id}/approve`, `/approvals/{id}/revoke`, `/approvals/{id}/publish`.
   - `/api/v1/publications/runs`, `/api/v1/publications/pull-requests`.
   - `/api/v1/benchmarks/summary`, `/api/v1/benchmarks/report`, `/api/v1/benchmarks/runs`, `/api/v1/benchmarks/run`.
5. **Frontend Single-Page Application (`frontend/`)**:
   - `PublicationReviewPage`: Human approval review, binding manifest display, cryptographic patch SHA validation, PR publishing, and publication history.
   - `BenchmarkDashboardPage`: KPI metric cards, comparative ablation table, report viewer, and on-demand trigger.
   - Verified clean production build with Vite (`dist/assets/index-BVCRxVVs.js`).
6. **CLI Commands (`src/repocontinuum/cli.py`)**:
   - `repocontinuum publish request`, `approve`, `revoke`, `run`, `status`.
   - `repocontinuum benchmark run`, `report`.
7. **Architecture Decision Record (`docs/adr/0005-approved-pr-publishing-and-benchmark-evaluation.md`)**:
   - Formally documented separate publisher interface, invalidation gates, no auto-merge, and benchmark evaluation protocol.

### Test Suite (162 Passed, 2 Skipped, 0 Failed)
- Publisher Interface Tests: `tests/unit/test_github_publisher.py` (5 passed).
- Publication Approval & Invalidation Tests: `tests/unit/test_publication_approval.py` (7 passed).
- Benchmark Evaluator Tests: `tests/unit/test_benchmark_evaluator.py` (2 passed).
- Publication REST API Tests: `tests/api/test_api_publication.py` (2 passed).
- Benchmark REST API Tests: `tests/api/test_api_benchmarks.py` (2 passed).
- End-to-End Publication Workflow Tests: `tests/integration/test_publication_e2e.py` (1 passed).
- Full regression suite across Milestones 1-6: 162 passed, 2 skipped (Docker stopped, Gemini API key offline).



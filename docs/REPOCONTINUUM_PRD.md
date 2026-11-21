# RepoContinuum — Product Requirements Document (PRD)

**Document version:** 1.0  
**Prepared:** 21 November 2026  
**Status:** Approved design baseline for implementation planning; product is not yet implemented  
**Product name:** RepoContinuum  
**Product category:** Repository-aware software engineering agent / developer tool  
**Primary positioning:** Long-horizon software maintenance with dependency-aware planning, persistent task state and regression-aware verification  
**Initial platform:** Local-first CLI and FastAPI backend; Python repositories only  
**Intended implementation environment:** Windows development machine using Python 3.13 and Docker Desktop/WSL2 where available

---

## 1. Executive summary

RepoContinuum helps a developer maintain a software repository across multiple related issues. Instead of treating each coding request as an isolated prompt, it creates a continuing maintenance workflow that understands repository structure, records task dependencies, preserves earlier decisions and acceptance obligations, proposes bounded patches, runs checks in an isolated workspace and provides evidence for human review.

The product's core promise is:

> RepoContinuum keeps track of what changed, why it changed, what depends on it, which checks were run, what remains unverified, and whether a later change has broken earlier accepted behaviour.

The initial version will be deliberately narrow. It will support local Python repositories, Python AST-based indexing, task chains with explicit dependencies, persistent checkpoints, reviewable patches and deterministic verification. LLM-assisted patching, dashboard views, GitHub Issues and pull-request publication will be layered on only after the deterministic workflow is reliable.

RepoContinuum is not an unrestricted autonomous coding agent. It must not merge code or publish remote changes without explicit human approval.

## 2. Product vision and design principles

### 2.1 Vision

Build a trustworthy software-maintenance assistant that can carry engineering context across a sequence of dependent changes and make its work auditable.

### 2.2 Product principles

1. **Repository-aware, not prompt-only:** use an index of files, modules, symbols, imports and tests to ground plans.
2. **Stateful, not forgetful:** preserve tasks, decisions, patches, test obligations and checkpoints.
3. **Verification-led:** generated code is a proposal; test and policy results determine verified status.
4. **Human-controlled:** users approve plans and patches before consequential actions.
5. **Secure by default:** repository source, issues, test output and model output are untrusted data.
6. **Reproducible:** record commit SHAs, runtime/tool versions, commands, outcomes and model configuration.
7. **Incremental:** deliver a complete local vertical slice before adding broad language support or integrations.
8. **Evidence over claims:** every success report must show the checks, results, limitations and skipped steps.

## 3. Problem statement

Software maintenance is cumulative. A fix for one issue can change an API, module contract, data model or test assumption used by later work. An assistant that solves one issue in isolation can lose important context or introduce regressions while addressing subsequent tasks.

Example maintenance chain:

- Task A: Correct refresh-token validation.
- Task B: Update session renewal to use the corrected validation behaviour.
- Task C: Add expiry and refresh regression tests.
- Task D: Update an API response contract without breaking existing clients.

A task-by-task assistant may pass the newest test while breaking a requirement established earlier. RepoContinuum represents the work as a chain or directed acyclic graph (DAG), tracks active obligations, and re-runs earlier relevant checks after later patches.

## 4. Goals, non-goals and success definition

### 4.1 Product goals

- Import a local Git repository at a specific commit/ref.
- Index Python files, imports, classes, functions, methods and test files.
- Display index coverage, ignored paths and parse failures.
- Create maintenance chains containing tasks, acceptance criteria and dependencies.
- Produce an explainable task plan.
- Generate or import a bounded patch and bind it to an exact base commit.
- Apply patches only in a disposable working copy.
- Run approved commands and tests with time/resource limits.
- Record evidence for each verification check.
- Preserve task state and previously accepted obligations.
- Detect when later tasks break earlier requirements.
- Require human approval before GitHub writes or merge-related operations.

### 4.2 Non-goals for the first release

- Replacing an IDE or full software-development environment.
- Supporting every programming language.
- Automatically selecting and solving an entire issue backlog.
- Autonomous merge, deployment or production changes.
- Running arbitrary untrusted code in a shared public multi-tenant service.
- Building a multi-agent system merely to increase the number of agents.
- Introducing Kubernetes, Kafka, Neo4j or a vector database before a measured requirement exists.
- Claiming state-of-the-art performance or enterprise-grade isolation without evidence.

### 4.3 Definition of success

The first useful product release is successful when a developer can import a controlled Python repository, inspect its index, define a dependent task chain, review a plan, apply a patch in an isolated copy, run verification, preserve the outcome and prove that a later task has not silently broken earlier active obligations.

A generated code diff alone is not a successful task.

## 5. Target users and use cases

### 5.1 Primary persona — software engineer

A developer maintaining a Python application who needs help with a bounded group of connected bugs or small enhancements. They understand code review and want control over changes.

**Needs**
- Know which files and symbols are relevant.
- Understand task ordering and dependencies.
- Inspect exact patches before accepting them.
- See which tests ran, failed, were skipped or were not run.
- Resume work after interruptions without losing context.

### 5.2 Secondary persona — technical lead / reviewer

A lead who wants a traceable report of changes, risks, test evidence and outstanding work before approving a pull request.

### 5.3 Key jobs to be done

- “Help me understand the repository before changing it.”
- “Show me which task depends on another task.”
- “Keep earlier acceptance criteria alive while we work on later issues.”
- “Propose a small patch and show exactly what changed.”
- “Run relevant checks without executing repository code on the API host.”
- “Tell me honestly what was verified and what was not.”

## 6. Product experience and main workflow

### 6.1 Core workflow

1. **Create workspace:** select a local repository and a branch/commit.
2. **Validate repository:** check that the path is valid, Git is available and the selected commit can be resolved.
3. **Index repository:** list supported files, parse Python AST, extract symbols/imports and discover tests.
4. **Inspect index:** show summary counts, parser warnings, ignored directories and unsupported file types.
5. **Create chain:** enter tasks, acceptance criteria and known dependencies.
6. **Validate DAG:** reject cycles, missing dependencies and invalid task references.
7. **Generate plan:** identify candidate files/symbols/tests, risks, assumptions and execution strategy.
8. **Approve plan:** user confirms or edits task order and dependencies.
9. **Propose patch:** produce a patch in a disposable copy, tied to the exact base commit.
10. **Verify:** run allowlisted checks and tests with limits.
11. **Review evidence:** show diff, check results, logs and unresolved obligations.
12. **Accept or reject:** user accepts, rejects or requests a bounded revision.
13. **Checkpoint:** persist state, including previous active obligations.
14. **Continue chain:** next task uses the accepted prior state and receives the obligation ledger.
15. **Publish (later release):** create a branch and PR only after explicit approval.

### 6.2 Primary interface for initial release

The first release is CLI-first, with a documented local API. Example commands:

```bash
repocontinuum repo add --path ./sample-service
repocontinuum repo index --repo <repository-id>
repocontinuum repo report --repo <repository-id>
repocontinuum chain create --repo <repository-id> --file ./maintenance-chain.yaml
repocontinuum chain plan --chain <chain-id>
repocontinuum chain status --chain <chain-id>
repocontinuum task report --task <task-id>
```

Exact command syntax may be refined during implementation, but commands must be consistent and documented. Do not create placeholder commands that do nothing.

## 7. Scope and release plan

### Release 0 — deterministic engineering foundation (first complete vertical slice)

**In scope**
- Local repository import.
- Exact commit/ref capture.
- Python file inventory and ignore rules.
- AST-based indexing of modules, imports, classes, functions and methods.
- Test-file and test-function discovery.
- Machine-readable and human-readable index reports.
- Maintenance chain/task data model.
- Explicit dependencies and DAG validation.
- Obligation ledger for acceptance criteria.
- Deterministic planning without a live LLM.
- Patch storage and safe patch-application abstraction.
- Isolated verification interface and evidence report.
- Persistence and resume/checkpoint behaviour.
- CLI and local API.
- Unit, integration and security-focused tests.

**Exit gate:** a controlled two- or three-task Python maintenance chain can be planned, patched and verified end to end; later changes trigger re-verification of active earlier obligations.

### Release 1 — bounded LLM-assisted patching

- Provider adapter interface.
- Deterministic fake provider for tests.
- Structured planning and patch-intent outputs.
- Context builder using repository index and targeted search.
- Bounded tool allowlist and repair attempts.
- Model/provider, prompt version, latency and cost metadata.
- Explicit approval before a patch is applied or accepted.

**Exit gate:** model suggestions can be schema-validated and tested, while deterministic verification remains authoritative.

### Release 2 — web dashboard and GitHub read integration

- React/TypeScript dashboard.
- Repository, task-chain and run views.
- GitHub App read permissions.
- Issue import and webhook handling.
- Idempotent asynchronous event processing.

**Exit gate:** connect a test repository and import issues without remote writes.

### Release 3 — safe PR publication

- User-approved branch creation.
- Patch publication and PR creation.
- Test/evidence summary in PR.
- Optional GitHub Checks integration.
- Approval/audit records bound to the exact patch hash and base ref.

**Exit gate:** approved patches can be published to a test repository; automatic merge remains disabled.

### Explicitly deferred

Multi-language call graphs, autonomous backlog processing, auto-merge, auto-deploy, multi-agent orchestration, vector databases, Kubernetes, Kafka, Neo4j and public multi-tenant arbitrary-code execution.

## 8. Functional requirements

Priority definitions: **P0** = required for Release 0; **P1** = required for Release 1; **P2** = later release.

| ID | Priority | Requirement | Acceptance evidence |
|---|---|---|---|
| FR-01 | P0 | Import local Git repository | Record canonical local path, selected ref and resolved commit SHA |
| FR-02 | P0 | Validate repository and workspace boundaries | Reject invalid path, unsafe symlink/path escape and invalid Git worktree |
| FR-03 | P0 | Inventory tracked/eligible files | Report supported, ignored, oversized, binary and skipped files |
| FR-04 | P0 | Parse Python AST | Extract modules, imports, classes, functions, methods and source ranges |
| FR-05 | P0 | Discover tests | Identify common pytest files/classes/functions and candidate source links |
| FR-06 | P0 | Persist repository index snapshot | Snapshot tied to repo ID, commit SHA, parser version and configuration |
| FR-07 | P0 | Create task chain | Store tasks, descriptions, acceptance criteria and stable IDs |
| FR-08 | P0 | Model dependencies | Create directed edges and validate topological order; reject cycles |
| FR-09 | P0 | Generate explainable plan | Show task order, relevant files/symbols/tests, assumptions and risks |
| FR-10 | P0 | Store patch proposal | Store patch, hash, task ID, base SHA and changed paths |
| FR-11 | P0 | Validate patch paths | Reject traversal, absolute paths and policy-protected paths |
| FR-12 | P0 | Apply patch in disposable copy | Original source tree remains unchanged |
| FR-13 | P0 | Execute verification | Record command, image/runtime identity, exit code, duration and output reference |
| FR-14 | P0 | Persist obligation ledger | Track acceptance obligations as active, superseded or withdrawn with reason |
| FR-15 | P0 | Re-run earlier obligations | Later task verification checks active earlier obligations |
| FR-16 | P0 | Produce evidence report | Distinguish passed, failed, skipped, not-run and inconclusive checks |
| FR-17 | P0 | Resume from checkpoint | Process restart does not lose committed task/chain state |
| FR-18 | P0 | Human approval gate | Reject/accept decisions are explicit and auditable |
| FR-19 | P1 | LLM provider adapter | Provider can be replaced without changing domain logic |
| FR-20 | P1 | Schema-validate model output | Invalid structured output cannot invoke tools or mutate workspace |
| FR-21 | P1 | Bounded patch repair | Enforce attempt, time, token and cost budgets |
| FR-22 | P2 | GitHub issue read integration | Import issue metadata and source links with least privilege |
| FR-23 | P2 | Webhook processing | Verify signature, deduplicate delivery and enqueue quickly |
| FR-24 | P2 | PR publication | Publish exact approved patch only after fresh base/hash validation |
| FR-25 | P2 | Checks reporting | Create checks only with a GitHub App and explicit Checks write permission |

## 9. Non-functional requirements

### 9.1 Security

- Treat repository files, issue descriptions, model responses and test output as untrusted data.
- Do not execute repository code in the FastAPI process.
- Do not pass host environment variables or credentials into a sandbox.
- Do not mount the Docker socket into executed workloads.
- Run a non-root process where supported; use read-only base image/filesystem where practical, default seccomp, dropped capabilities, `no-new-privileges`, and CPU/memory/PID/time limits.
- Disable network access in test execution by default; require an explicit, documented allowlist for tests that need network.
- Reject path traversal and writes outside the disposable repository workspace.
- Protect `.git`, private key files, environment files and CI/security configuration paths according to an explicit policy.
- Never include secrets in prompts, test output, trace attributes or logs.
- No PR publication, merge or deployment without explicit human approval.
- Docker containers improve isolation but are not a proof of safety for arbitrary hostile code. Public multi-tenant execution is out of scope until a stronger isolation design and security review exist.

### 9.2 Reliability and reproducibility

- Store repository URL/path identifier, exact commit SHA, branch/ref, parser version and index configuration.
- Store patch hash, base SHA, check command, environment/image digest, exit code and timestamps.
- Make task state transitions transactional.
- Use idempotency keys for retried worker jobs.
- Never mark a task verified if required checks were skipped, timed out or not run.
- Keep a durable checkpoint before starting the next task.

### 9.3 Performance

No arbitrary performance promise is made before baseline measurement. Record indexing duration, files parsed, parse failures, graph build duration, selected-test count, verification runtime and memory use. The first release should handle small/medium Python repositories within configurable limits and report when limits are exceeded.

### 9.4 Maintainability

- Use typed domain models and explicit interfaces.
- Keep provider, parser, patch runner and sandbox behind adapters.
- Use Alembic for schema migrations once database persistence is introduced.
- Keep business logic independent of FastAPI routes and CLI rendering.
- Pin dependencies and maintain a reproducible lockfile.
- Use structured JSON logs and clear error categories.

### 9.5 Accessibility and usability

- CLI output must be readable without colour.
- Reports must be exportable as JSON and Markdown.
- Every check must state why it ran or why it was skipped.
- Display warnings and unsupported constructs instead of silently omitting them.

## 10. Technical architecture and constraints

### 10.1 Deployment shape

Start with a modular monolith plus a separate worker process. Do not split into microservices in the first release.

```text
CLI / Local API client
        |
     FastAPI
        |
  Domain/application services
        |
 PostgreSQL (durable state)
        |
 Redis + RQ (when async task execution is added)
        |
 Worker process
        |
 Repository index / planner / patch workflow
        |
 Disposable verification workspace
        |
 Evidence report + human approval gate
```

### 10.2 Recommended technology choices

| Layer | Choice | Constraint |
|---|---|---|
| Runtime | Python 3.13 initially | Pin exact patch version after checking local environment and dependency compatibility |
| API | FastAPI + Pydantic v2 | Keep route handlers thin |
| Persistence | SQLAlchemy 2.x + Alembic + PostgreSQL | PostgreSQL is canonical; test repositories may use isolated test DBs |
| CLI | Typer | CLI invokes application services, not duplicated business logic |
| Python parsing | Standard-library `ast` | First parser for Release 0 |
| Multi-language parsing | Tree-sitter | Add only after Python vertical slice |
| Graph | NetworkX / in-memory DAG | No graph DB in Release 0 |
| Search | Symbol/import/test index + ripgrep/text search | No vector DB required initially |
| Queue | Redis + RQ | Add when long-running worker tasks are implemented |
| Verification | Pytest, Ruff, Pyright or mypy, Semgrep | Commands must be explicit and allowlisted |
| Sandbox | Disposable Linux container or stronger dedicated worker | No host secrets, no privileged mode, no Docker socket |
| UI | React + TypeScript + Vite | Release 2 only |
| Observability | JSON logs; OpenTelemetry later | Correlate chain, task and run IDs |

## 11. Core domain model

| Entity | Essential fields |
|---|---|
| Repository | id, name, source_path, remote_url, default_ref, created_at |
| RepositorySnapshot | id, repository_id, commit_sha, ref_name, indexer_version, parser_version, indexed_at, status |
| IndexedFile | id, snapshot_id, path, language, size_bytes, parse_status, content_hash |
| Symbol | id, file_id, qualified_name, kind, start_line, end_line, docstring |
| ImportEdge | id, snapshot_id, source_module, target_module, resolution_status, provenance |
| TestCase | id, file_id, qualified_name, linked_symbols, discovery_method |
| TaskChain | id, repository_id, base_snapshot_id, title, status, created_at |
| MaintenanceTask | id, chain_id, title, description, order_index, status, acceptance_criteria |
| TaskDependency | id, predecessor_task_id, successor_task_id, source, approved_by |
| Obligation | id, chain_id, task_id, description, status, verifier_ref, status_reason |
| AgentRun | id, task_id, provider, model, prompt_version, status, started_at, ended_at, usage_metadata |
| Patch | id, task_id, base_sha, patch_hash, diff_path, changed_paths, status |
| VerificationRun | id, patch_id, environment_digest, started_at, ended_at, status |
| VerificationCheck | id, verification_run_id, name, command, result, exit_code, duration_ms, output_ref |
| Approval | id, patch_id, patch_hash, base_ref, decision, actor, decided_at |
| AuditEvent | id, chain_id, task_id, actor_type, action, metadata, occurred_at |

Obligations must have explicit lifecycle states: `active`, `superseded`, or `withdrawn`. A task failure must not cause an obligation to disappear. Only an explicit, recorded specification change may supersede or withdraw it.

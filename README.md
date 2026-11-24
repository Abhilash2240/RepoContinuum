# RepoContinuum

RepoContinuum is a local-first, repository-aware software maintenance assistant that manages multiple dependent tasks in a codebase with long-horizon state, dependency-aware planning, regression-aware verification, and strict human control.

---

## Current Status: All Six Milestones Complete (Milestones 1–6)

- **Milestone 1 (Repository Intelligence Foundation):**
  - Walks repository files with strict path-traversal and symlink escape checks.
  - Safely ignores standard virtual environments, build artifacts, caches, binaries, and oversized files.
  - Extracts module-level, class-level, function-level, and method-level AST metadata with zero code execution.
  - Discovers docstrings, un-evaluated type annotations, parameter signatures, and decorators.
  - Resolves imports (standard library, relative, internal, third-party) and highlights dynamic/unresolved imports.
  - Discovers pytest test files, test classes, and test functions, with heuristic source-module links.
  - Emits reproducible JSON index snapshots and human-readable terminal reports.

- **Milestone 2 (Task Chains & Obligation Ledger):**
  - Models complex multi-task maintenance work as a Directed Acyclic Graph (DAG) with NetworkX.
  - Detects cycles and missing dependencies, enforcing stable lexicographical topological execution order.
  - Tracks task lifecycle states (`CREATED`, `READY`, `PLANNED`, `BLOCKED`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `CANCELLED`).
  - Gated transitions: blocked tasks cannot begin until all predecessors are completed or explicitly waived.
  - Obligation ledger maintains acceptance criteria across tasks (`active`, `superseded`, `withdrawn`), strictly preserving obligations when tasks fail.
  - Atomic persistence with SQLAlchemy 2.x and Alembic migrations, with durable checkpoints surviving full process restarts.
  - Complete CLI commands for task chain authoring, dependency linking, DAG planning, and resumption.

- **Milestone 3 (Patch Generation and Isolated Verification):**
  - Strict unified diff parser extracting changed files, hunk geometries, additions, and removals with SHA-256 integrity hash verification.
  - Path traversal and security validator rejecting `../`, absolute paths, Windows drive paths, duplicate targets, and sensitive/credential files (`.git`, `.env*`, `.github*`, keys/certs).
  - Isolated disposable working-copy manager provisioning clean source trees at exact base commit SHAs without dirtying the host workspace.
  - Strict command execution allowlist (`py_compile`, `pytest`, `ruff`) with secret redaction (JWT, API keys, private keys) and zero `shell=True` execution.
  - Disposable Linux container sandbox (`DockerSandboxRunner`) with `--network none`, `--read-only`, dropped capabilities, seccomp filters, and **fail-closed security** (never falls back to host execution when Docker is unavailable).
  - Regression gate re-verifying active obligations from earlier tasks, detecting broken invariants (`REGRESSION_DETECTED`), and honestly reporting inconclusive verifiers (`INCONCLUSIVE`).
  - Full provenance and evidence reporting stored in database and rendered in formatted Markdown.

- **Milestone 4 (LLM Provider Integration & Bounded Agent):**
  - Provider-agnostic LLM interface with Google Gemini (`google-genai` SDK), OpenRouter (`particle-ai/particle-1:free` via OpenAI-compatible API), and deterministic `FakeLLMProvider`.
  - Strongly-typed Pydantic schemas (`IssueAnalysis`, `TaskPlan`, `PatchProposal`, `ToolIntent`).
  - Context builder with prompt-injection defense via `<UNTRUSTED_REPOSITORY_DATA>` boundary encapsulation.
  - Bounded read-only tool dispatcher with closed allowlist, traversal guards, sensitive file blocking, and call budgets.
  - Mandatory human-in-the-loop plan approval gate before patch proposal and verification.
  - Bounded repair loop with automated regression feedback and budget limit protection (`BUDGET_EXHAUSTED`).

- **Milestone 5 (Dashboard & GitHub Read Integration):**
  - Local-first web dashboard (React 18, TypeScript, Vite, Lucide React) served directly by FastAPI at `127.0.0.1:8000`.
  - Rich views for Overview metrics, Repository Explorer, Task Chain & DAG Visualizer, Obligation Ledger, Agent Telemetry, and Verification Evidence.
  - Strict read-only GitHub App integration (RS256 JWT, cached installation tokens, zero write methods).
  - HMAC-SHA256 webhook signature verification (`X-Hub-Signature-256`) with `hmac.compare_digest`.
  - Webhook delivery idempotency with `X-GitHub-Delivery` tracking in database.
  - Safe import of GitHub issues into task chains wrapped in `<UNTRUSTED_REPOSITORY_DATA source="github_issue">` boundary tags.

- **Milestone 6 (Approved PR Publishing & Benchmark Evaluation):**
  - Separate GitHub write publisher (`BaseGitHubPublisher` / `LiveGitHubPublisher` / `FakeGitHubPublisher`) restricted strictly to branch creation, commit publishing, and PR creation.
  - Prohibited methods (`merge_pull_request`, `delete_branch`, `force_push`, etc.) omitted from the publisher interface and verified via automated reflection tests.
  - Cryptographic patch-hash (SHA-256) and base-commit binding via `PublicationApproval` and `PublicationApprovalPolicy`.
  - Immediate invalidation of approvals if patch hash changes, base commit moves, target branch differs, approval expires, or verification detects regressions.
  - Standardized PR descriptions including task description, changed files, verification evidence, regression status, limitations, and reproducibility metadata.
  - Idempotent branch and PR publishing with network retry resilience.
  - Zero auto-merge and zero auto-deployment guarantees.
  - Reproducible benchmark evaluation harness (`benchmarks/`): 10 multi-task chains (22 sequential maintenance tasks) across 3 comparable ablation baselines (A: Isolated, B: Planning Only, C: Full RepoContinuum).
  - Explicit reporting of all 12 evaluation metrics with transparent numerators and denominators.
  - Dashboard views for Publication Review (`PublicationReviewPage`) and Benchmark Dashboard (`BenchmarkDashboardPage`).

---

## Requirements & Setup

- **Python:** Python 3.13 or newer.
- **Git:** Git 2.30+ installed.

### Installation

Install the package in development mode:
```powershell
# From the RepoContinuum directory (core dependencies + testing tools)
python -m pip install -e ".[dev]"

# Optional: To include Google Gemini SDK support
python -m pip install -e ".[gemini]"
```

---

## CLI Usage

### 1. Index a Python Repository

Scan and index a repository, outputting a rich terminal summary and a machine-readable JSON snapshot:

```powershell
python -m repocontinuum.cli repo index --path "C:\path\to\your\python-repo" --output repo_snapshot.json
```

Or using the installed console script:
```powershell
repocontinuum repo index --path ./my-service --output snapshot.json
```

### 2. Inspect an Index Snapshot

View a human-readable report from an existing JSON snapshot:
```powershell
repocontinuum repo report --snapshot snapshot.json
```

### 3. Check Version & Environment

```powershell
repocontinuum version
```

---

## Running the Test Suite

Execute the full suite of unit, integration, and security tests:
```powershell
python -m pytest tests/ -v
```

---

## Architecture & Security

- **Zero Host Execution:** The repository indexer relies entirely on `ast.parse`. It never invokes `importlib`, `exec`, or `eval` on scanned repository code.
- **Path Traversal Protection:** All filesystem operations canonicalize paths and verify subordination to the designated repository root. Symlinks escaping root are logged and skipped.
- **Immutable Snapshots:** Repository index snapshots are deterministic and tied to the exact Git commit SHA and parser configuration.

For full architecture and design decisions, see:
- [Product Requirements Document (PRD)](docs/REPOCONTINUUM_PRD.md)
- [Implementation Plan](docs/IMPLEMENTATION_PLAN.md)
- [Security Policy](docs/SECURITY.md)
- [ADR 0001: Indexer Architecture](docs/adr/0001-indexer-architecture.md)
- [ADR 0002: Sandbox & Verification Architecture](docs/adr/0002-sandbox-and-verification-architecture.md)


---

## Task Chain & Obligation CLI Commands (Milestone 2)

### 1. Create a Task Chain
```powershell
repocontinuum chain create --title "Refactor Auth and Session Renewal" --repo "my-service"
```

### 2. Add Tasks with Acceptance Obligations
```powershell
repocontinuum chain task-add --chain chn-abc123def456 --title "Task 1: Fix refresh token" --order 1 --criterion "Expired token returns 401" --criterion "Valid token refreshes session"

repocontinuum chain task-add --chain chn-abc123def456 --title "Task 2: Update session renewal handler" --order 2 --criterion "Session renewal handler uses new token logic"
```

### 3. Establish Directed Dependencies
```powershell
repocontinuum chain dep-add --chain chn-abc123def456 --pred tsk-111111111111 --succ tsk-222222222222
```

### 4. Validate Chain DAG & Cycle Detection
```powershell
repocontinuum chain validate --chain chn-abc123def456
```

### 5. View Stable Topological Execution Plan
```powershell
repocontinuum chain plan --chain chn-abc123def456
```

### 6. View Chain Status & Blocked Tasks
```powershell
repocontinuum chain status --chain chn-abc123def456
```

### 7. Inspect Acceptance Obligation Ledger
```powershell
repocontinuum chain obligations --chain chn-abc123def456
```

### 8. Create & Resume Checkpoints
```powershell
# Create an atomic checkpoint
repocontinuum chain checkpoint --chain chn-abc123def456

# Resume from durable state
repocontinuum chain resume --chain chn-abc123def456
```

---

## Patch & Verification CLI Commands (Milestone 3)

### 1. Validate a Unified Diff File
Inspect syntax, line counts, and path security without applying or executing code:
```powershell
repocontinuum patch validate --diff path/to/feature.patch
```

### 2. Propose a Patch for a Maintenance Task
Cryptographically bind a patch to a task and exact base commit SHA:
```powershell
repocontinuum patch propose --task tsk-111111111111 --diff path/to/feature.patch --base-sha a1b2c3d4e5f6...
```

### 3. Run Isolated Verification and Regression Checking
Execute tests in a disposable Linux container (or simulated test double) and re-verify earlier obligations:
```powershell
# Production isolated verification (fails closed if Docker is unavailable)
repocontinuum verify run --task tsk-111111111111 --patch pat-999999999999 --repo ./my-service

# Verification using high-speed deterministic test double (for testing without Docker)
repocontinuum verify run --task tsk-111111111111 --patch pat-999999999999 --repo ./my-service --fake-sandbox
```

### 4. Inspect Verification Evidence Report
Query and render full evidence, executed checks, earlier obligation results, and regression alerts:
```powershell
repocontinuum verify report --run vrun-123456789abc
```

---

## Database Migrations (Alembic)

To apply the latest database migrations:
```powershell
python -m alembic upgrade head
```

### 4. Bounded LLM Agent Workflow

#### LLM Provider Configuration

RepoContinuum supports multiple LLM providers configured via environment variables (`.env`):

1. **Offline / Fake Provider (Default):**
   ```env
   REPOCONTINUUM_LLM_PROVIDER=fake
   ```
2. **Google Gemini Provider:**
   ```env
   REPOCONTINUUM_LLM_PROVIDER=gemini
   GEMINI_API_KEY=your_gemini_api_key
   GEMINI_MODEL=gemini-2.5-flash
   ```
3. **OpenRouter Provider (Particle-1 Free):**
   ```env
   AI_PROVIDER=openrouter
   OPENROUTER_API_KEY=your_openrouter_api_key
   OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
   OPENROUTER_MODEL=particle-ai/particle-1:free
   OPENROUTER_SITE_URL=https://github.com/repocontinuum
   OPENROUTER_APP_NAME=RepoContinuum
   ```

Execute an end-to-end LLM-assisted maintenance workflow with mandatory human-in-the-loop plan approval:

```powershell
# 1. Analyze an issue using repository intelligence
python -m repocontinuum.cli agent analyze --task <task_id> --repo <repo_path>

# 2. Formulate a structured maintenance plan
python -m repocontinuum.cli agent plan --task <task_id> --run <run_id> --repo <repo_path>

# 3. Explicit human approval gate (mandatory before code generation)
python -m repocontinuum.cli agent approve-plan --task <task_id> --run <run_id> --approver "developer-name"

# 4. Propose a reviewable unified diff patch
python -m repocontinuum.cli agent propose --task <task_id> --run <run_id> --repo <repo_path>

# 5. Verify in isolated disposable sandbox (with automated repair if needed)
python -m repocontinuum.cli agent verify --task <task_id> --run <run_id> --repo <repo_path>

# 6. View agent run status and comprehensive report
python -m repocontinuum.cli agent status --run <run_id>
python -m repocontinuum.cli agent report --run <run_id>
```

---

## Web Dashboard & GitHub Integration (Milestone 5)

Launch the integrated local web dashboard and API server:

```powershell
# Launch dashboard on default loopback (127.0.0.1:8000)
repocontinuum dashboard run

# Or specify custom host, port, or development auto-reload
repocontinuum dashboard run --host 127.0.0.1 --port 8000 --reload
```

Once started, open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser to access:
- **Operations Center Overview:** Metric cards, task distributions, obligation breakdown, recent runs, regression alerts.
- **Repository Explorer:** File tree navigation, AST symbol search with docstrings, signatures, and locations.
- **Task Chains & DAG Visualizer:** Interactive dependency graph with cycle-free topological order visualization.
- **Obligation Ledger:** Active vs superseded vs withdrawn requirements ledger.
- **Agent Telemetry:** Step-by-step LLM run traces, prompt/completion token usage, and latency.
- **Verification Evidence Viewer:** Test check outcomes, pass/fail results, and formatted Markdown reports.
- **GitHub Read Explorer:** Read-only access to GitHub App installations, repositories, issues, and pull requests, with safe one-click import into task chains.
- **Publication Review:** Human approval gate showing cryptographic patch SHA-256 hash, base commit SHA, target branch, verification verdict, zero-regression status, PR markdown preview, and one-click publishing.
- **Benchmark Dashboard:** Comparative ablation metrics across Baselines A, B, and C with on-demand experiment trigger and markdown report viewer.

---

## Approved GitHub Pull Request Publishing (Milestone 6)

Manage human approvals and publish verified maintenance patches to GitHub:

```powershell
# 1. Request publication approval for a verified task
repocontinuum publish request --task <task_id> --chain <chain_id> --patch <patch_id> --run <vrun_id> --owner <owner> --repo <repo>

# 2. Inspect pending publication approvals
repocontinuum publish status

# 3. Explicit human approval grant (binds to exact patch hash and base commit)
repocontinuum publish approve --approval <approval_id> --approver "senior-eng@company.com" --hours 48

# 4. Publish approved patch as GitHub Pull Request (idempotent, no auto-merge)
repocontinuum publish run --approval <approval_id>

# 5. Revoke approval if needed prior to publication
repocontinuum publish revoke --approval <approval_id> --revoker "eng-lead@company.com" --reason "Design review requested changes"
```

---

## Benchmark Evaluation Harness (Milestone 6)

Run the reproducible benchmark evaluation across the 10-chain corpus (22 tasks) and compare baselines:

```powershell
# Run evaluation across all three baselines (A: Isolated, B: Planning, C: Full RepoContinuum)
repocontinuum benchmark run --baseline all --seed 42

# View the formatted comparative Markdown evaluation report
repocontinuum benchmark report
```



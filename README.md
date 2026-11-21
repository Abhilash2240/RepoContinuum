# RepoContinuum

RepoContinuum is a local-first, repository-aware software maintenance assistant that manages multiple dependent tasks in a codebase with long-horizon state, dependency-aware planning, regression-aware verification, and strict human control.

---

## Current Status: Milestone 1 & Milestone 2 Complete

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

---

## Requirements & Setup

- **Python:** Python 3.13 or newer.
- **Git:** Git 2.30+ installed.

### Installation

Install the package in development mode:
```powershell
# From the RepoContinuum directory
python -m pip install -e .
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
- [Product Requirements Document (PRD)](file:///docs/REPOCONTINUUM_PRD.md)
- [Implementation Plan](file:///docs/IMPLEMENTATION_PLAN.md)
- [Security Policy](file:///docs/SECURITY.md)
- [ADR 0001: Indexer Architecture](file:///docs/adr/0001-indexer-architecture.md)


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

## Database Migrations (Alembic)

To apply the latest database migrations:
```powershell
python -m alembic upgrade head
```

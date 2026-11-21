# RepoContinuum — Implementation Plan

**Plan Version:** 1.0  
**Baseline Date:** 21 November 2026  
**Status:** In Progress (Phase 0 & Milestone 1 Active)  
**Target Platform:** Windows / Python 3.13 (Docker Desktop/WSL2 for sandboxing in Milestone 3)

---

## 1. Plan Overview and Phasing Strategy

RepoContinuum follows a strict milestone-driven, test-first, human-controlled delivery methodology. Features are implemented sequentially in bounded vertical slices. No milestone proceeds until the preceding milestone meets its complete Definition of Done, including unit, integration, and security tests.

```text
[Phase 0: Environment & Scaffold]  ──> COMPLETE
             │
             ▼
[Milestone 1: Repository Intelligence Foundation] ──> COMPLETE
             │
             ▼
[Milestone 2: Task Chains & Obligation Ledger] ──> COMPLETE ◄── CURRENT FOCUS
             │
             ▼
[Milestone 3: Patch & Isolated Verification Loop]
             │
             ▼
[Milestone 4: LLM Provider & Bounded Agent]
             │
             ▼
[Milestone 5: Dashboard & GitHub Read Integration]
             │
             ▼
[Milestone 6: Approved PR Publication & Benchmarking]
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

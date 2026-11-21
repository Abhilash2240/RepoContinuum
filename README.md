# RepoContinuum

RepoContinuum is a local-first, repository-aware software maintenance assistant that manages multiple dependent tasks in a codebase with long-horizon state, dependency-aware planning, regression-aware verification, and strict human control.

---

## Current Status: Milestone 1 (Repository Intelligence Foundation)

Milestone 1 provides a safe, deterministic repository indexer for Python repositories:
- Walks repository files with strict path-traversal and symlink escape checks.
- Safely ignores standard virtual environments, build artifacts, caches, binaries, and oversized files.
- Extracts module-level, class-level, function-level, and method-level AST metadata with zero code execution.
- Discovers docstrings, un-evaluated type annotations, parameter signatures, and decorators.
- Resolves imports (standard library, relative, internal, third-party) and highlights dynamic/unresolved imports.
- Discovers pytest test files, test classes, and test functions, with heuristic source-module links.
- Emits reproducible JSON index snapshots and human-readable terminal reports.

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

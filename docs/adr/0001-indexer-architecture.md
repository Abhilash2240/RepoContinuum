# ADR 0001: AST-Based Python Repository Indexer Architecture

**Date:** 21 November 2026  
**Status:** Accepted  
**Deciders:** Core Engineering Team  

---

## Context
RepoContinuum requires a repository intelligence foundation that extracts module, class, function, method, decorator, parameter, docstring, import, and test metadata from Python repositories. The primary technical requirements are:
1. Zero code execution: Scanned code must never be imported or executed.
2. Robust error containment: A syntax error in one file must not crash the indexer.
3. High fidelity: Qualified names, line/column source ranges, and un-evaluated annotations must be captured.
4. Determinism: Successive scans of the same commit and configuration must produce identical snapshot hashes.
5. Windows and Linux compatibility with POSIX-normalized relative paths.

## Decision
1. **Parser Engine:** Use Python's built-in standard library `ast` module. It is robust, maintained with Python 3.13, requires no native C dependencies or external compiler toolchains, and provides safe parse-only semantics without executing module-level code.
2. **Data Modeling:** Use Pydantic v2 schemas (`pydantic.BaseModel`) with frozen immutable snapshots. All paths stored in schemas are normalized POSIX relative strings.
3. **Dual-Mode Git Resolution:** Support dual-mode Git ref and commit SHA resolution:
   - Primary: Subprocess `git rev-parse HEAD` and `git symbolic-ref --short HEAD`.
   - Fallback: Pure-Python direct `.git` file parser (reads `.git/HEAD`, `.git/refs/heads/*`, `.git/packed-refs`). This guarantees commit SHA resolution even in restricted sandbox environments or environments without Git binary on PATH.
4. **Safety & Traversal:** Filesystem traversal uses canonical root verification (`Path.resolve()`) to ensure no file path escapes the repository boundary. Binary detection inspects initial byte buffers for null characters. Oversized files exceeding configurable thresholds are skipped with explicit audit records.
5. **CLI Framework:** Use Typer with Rich for clear, formatted CLI reports and machine-readable JSON exports.

## Consequences
- **Positive:** Zero risk of arbitrary code execution during indexing; full determinism; zero heavy external dependencies; cross-platform consistency.
- **Negative / Limitations:** Python static AST analysis cannot resolve dynamic runtime imports (e.g. `importlib.import_module(var)`) or metaprogrammed attributes. These limitations are surfaced explicitly as `dynamic` or `unresolved` with documented uncertainty rather than guessing.

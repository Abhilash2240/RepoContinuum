# ADR 0002: Patch Generation, Disposable Workspace, and Isolated Verification Architecture

## Status
Accepted

## Context
RepoContinuum assists developers by proposing and validating bounded patches across multi-task maintenance chains. Because maintenance changes may contain subtle syntax defects, break existing invariants, or be generated from untrusted external sources, applying patches and executing tests directly on the host machine or original working tree presents severe security and stability risks:
1. Untrusted patches could perform path traversal (`../`), overwrite system credentials, or tamper with `.git` internals.
2. Running test suites or verification commands on the host machine could execute arbitrary hostile code (e.g., repository setup scripts, malicious test fixtures, or dynamic imports).
3. Modifying the host working directory in-place risks corrupting unstaged changes or leaving the repository in a dirty, inconsistent state.
4. Later tasks in a dependent chain could inadvertently break acceptance obligations satisfied by earlier tasks without immediate detection.

## Decision

We have established the following architectural decisions for Milestone 3 (Patch Generation and Isolated Verification):

### 1. Strict Unified Diff Parser & Content Integrity
- Patches must adhere to the standard unified diff format (`diff -u`).
- The parser validates file headers (`---`, `+++`), hunk headers (`@@ -l,s +l,s @@`), context lines, additions, and removals.
- Every patch computes a cryptographic SHA-256 content hash upon ingestion. Any mismatch between recorded and computed hash fails closed before any workspace operation.
- Patches are bound to: Repository ID, Task ID, Base Commit SHA, Patch SHA-256 Hash, and Changed Path list.

### 2. Filesystem & Path Containment Security
- All target file paths inside a diff are inspected prior to workspace creation.
- Paths with directory traversal (`../`, `..\`), absolute paths (`/etc/...`, `C:\...`), and Windows drive letters are unconditionally rejected.
- Protected files are strictly blocked from patch modification:
  - Repository internals: `.git/**`
  - Secrets & environments: `.env*`, `*.pem`, `*.key`, `id_rsa*`
  - Critical CI workflows: `.github/**`
- Duplicate patch targets and unexpected binary diffs are rejected.

### 3. Disposable Working Copy Manager
- The host working directory is **never modified** during patch evaluation or verification.
- A disposable isolated workspace is provisioned in a temporary directory by copying the repository tree at the exact base commit SHA, strictly excluding `.git` and `.env*` files.
- The base commit SHA of the target repository is verified before applying any patch.
- Deterministic cleanup is guaranteed via context manager semantics and exception handlers.

### 4. Command Allowlist Policy
- Only allowlisted verification profiles are permissible (e.g. `python -m py_compile`, `python -m pytest`, `python -m ruff`).
- Commands are passed strictly as structured argument arrays (`List[str]`). Subprocess calls never use `shell=True`.
- Shell operators (`&&`, `||`, `;`, `|`, `>`, `<`), command substitutions (`$()`, `` ` ``), and wildcard globbing are rejected.
- All command outputs (stdout/stderr) are passed through an active secret redactor prior to persistence or display.

### 5. Restricted Docker Sandbox with Fail-Closed Security
- Verification commands run inside isolated disposable Linux containers (`python:3.13-slim`).
- Security flags: `--network none` (no external ingress/egress), `--read-only` root filesystem (writable `/tmp` tmpfs), dropped Linux capabilities (`--cap-drop ALL`), default seccomp profile, CPU limits (`--cpus 2.0`), memory limits (`--memory 2g`), and wall-clock execution timeouts.
- **Fail-Closed Guarantee:** If the Docker daemon is unreachable or stopped, the system strictly refuses to execute repository code on the host. The verification check records `status=NOT_RUN` / `conclusion=NOT_RUN` and the run fails closed.

### 6. Regression Detection Gate via Obligation Re-verification
- For any patch proposed on a task in a chain, the verification engine re-runs all active obligations established by earlier tasks.
- If an earlier active obligation fails its executable verifier, the run is flagged as `status=REGRESSION_DETECTED` and `conclusion=FAILED`.
- If an obligation lacks an executable verifier reference, the result is reported honestly as `INCONCLUSIVE` rather than fabricating success.
- Comprehensive `EvidenceReport` records are stored in PostgreSQL/SQLite and rendered in markdown and terminal UI.

## Consequences

### Positive
- Host repository working tree remains pristine and immune to corrupted patches.
- Arbitrary code execution on developer machines is prevented by isolated containerization and static allowlists.
- Regressions across multi-step maintenance chains are detected immediately upon patch evaluation.
- Full provenance and auditable evidence reports ensure human developers retain complete control.

### Limitations
- Requires Docker Desktop / container engine running to execute containerized tests (falls closed with `NOT_RUN` when unavailable).
- Fake sandbox runner is provided for unit and local integration testing without requiring a live Docker daemon.

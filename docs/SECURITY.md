# RepoContinuum — Security Policy and Architecture

**Version:** 1.2  
**Effective Date:** 21 November 2026

---

## 1. Security Philosophy

Security in RepoContinuum is a core product capability, not a cosmetic post-implementation audit. The system interacts with untrusted repository code, external issue descriptions, user patches, and automated test runners.

**Guiding Axiom:** All repository contents, issue descriptions, generated diffs, and test outputs are treated as **untrusted data**.

---

## 2. Threat Model and Boundary Analysis

| Asset / Boundary | Threat | Mitigation Policy |
|---|---|---|
| **Repository File Indexing** | Code execution during parsing (e.g. `importlib`, `exec`, `eval`) | Static AST parsing via standard library `ast.parse` only. Target repository code is **never imported or executed** on the host. |
| **Filesystem Access** | Path traversal (`../`), symlink escapes, arbitrary file disclosure | Strict canonical path validation (`Path.resolve()`). Inspected files must be strictly subordinate to the repository root. Symlinks escaping root are logged and skipped. |
| **Protected Files** | Modifying sensitive system files or credentials | Explicit protection of `.git`, `.env*`, SSH keys, cloud credentials, and CI workflows. |
| **Patch Ingestion & Parsing** | Malformed diffs, path traversal, host file overwrites | Strict unified diff parser validating hunk geometry, headers, and computing SHA-256 integrity hash. All target paths inspected against path traversal, Windows drive letters, and protected paths. |
| **Workspace Isolation** | Corrupting user's active branch or unstaged working tree | Disposable working copies created in temporary directories at the exact base commit SHA, strictly excluding `.git` and `.env*`. Host repository is never modified during verification. |
| **Verification Execution** | Hostile setup or test scripts executing malicious payloads | Strict command allowlist (`python -m py_compile`, `python -m pytest`, `python -m ruff`). Subprocess invocation strictly uses argument arrays without `shell=True`. |
| **Sandbox Execution** | Container breakout, network exfiltration, resource exhaustion | Disposable Linux containers with `--network none`, `--read-only`, dropped capabilities (`--cap-drop ALL`), seccomp filter, memory/CPU limits, and timeout enforcement. |
| **Sandbox Availability** | Host fallback when Docker daemon is stopped | **Fail-Closed Guarantee:** Verification immediately returns `NOT_RUN` / `FAILED` if the container engine is unavailable. It strictly **never falls back to host execution**. |
| **Regression Prevention** | Undetected breaking changes to earlier tasks in chain | Re-runs active acceptance obligations established by earlier tasks. Flags regressions as `REGRESSION_DETECTED`. Lacking verifiers reported honestly as `INCONCLUSIVE`. |
| **Credential Redaction** | Secret leakage in logs, audit records, or reports | Active redaction of JWTs, bearer tokens, private keys, AWS keys, and generic API keys across stdout and stderr. |
| **Consequential Remote Actions** | Unauthorized commits, PR creations, or deployments | Human-in-the-loop gate required for all remote GitHub writes. No auto-merge or auto-deploy. |

---

## 3. Indexer Security Invariants (Milestone 1)

1. **Zero Execution Guarantee:** The indexer operates purely as an AST parser. It does not invoke Python's module loader, does not evaluate type annotations, and does not evaluate decorator expressions.
2. **Deterministic Error Containment:** Malformed, hostile, or binary files encounter strict exception boundaries. An attacker cannot cause a denial-of-service on the indexing service by supplying a syntactically invalid or recursive file.
3. **Secret Redaction & Boundary Isolation:** The indexer ignores environment files (`.env*`), private keys, and credential stores. Absolute paths from the host machine are normalized to POSIX relative paths within snapshots to avoid leaking host filesystem metadata.

---

## 4. Patch & Verification Invariants (Milestone 3)

1. **Patch Integrity Binding:** Every patch is cryptographically bound to its Repository ID, Task ID, Base Commit SHA, and SHA-256 Patch Content Hash.
2. **No Host Code Execution:** Repository test execution must occur within an isolated container environment or simulated test double. Repository test suites are never executed directly on the host OS.
3. **Fail-Closed Container Engine:** If Docker Desktop is stopped or unreachable, the system records `status=NOT_RUN` and halts verification. Host execution is strictly forbidden.
4. **Active Obligation Preservation:** Obligations from failed tasks are never silently removed. Regression checks against earlier active obligations prevent cascading silent failures.

---


---

## 5. LLM Integration and Prompt-Injection Defense (Milestone 4)

1. **Untrusted Data Boundary Tags:**
   - All external, user-supplied, and repository-derived data (issue descriptions, bug comments, AST docstrings, file contents) are enclosed inside explicit boundary delimiters:
     `<UNTRUSTED_REPOSITORY_DATA source="..."> ... </UNTRUSTED_REPOSITORY_DATA>`
   - System prompts instruct the LLM that content within these tags represents untrusted passive data that must never be interpreted as instructions, system directives, or command overrides.

2. **Bounded Read-Only Tool Execution:**
   - The tool dispatcher (`ToolDispatcher`) enforces a strict allowlist of 8 read-only inspection tools.
   - Shell execution (`bash`, `sh`, `powershell`, `cmd`), process execution (`subprocess`, `exec`, `eval`), arbitrary code execution, and remote networking are strictly prohibited.
   - Filesystem traversal (`../`), absolute paths, Windows drive paths, and access to protected files (`.git/**`, `.env*`, `*.key`, `*.pem`, `id_rsa*`, `.github/**`) are actively blocked.
   - Each tool invocation is bounded by a 32 KB output limit and an overall budget (default 10 calls per task).

3. **Mandatory Human Plan Approval Gate:**
   - The agent cannot generate patches or invoke verification autonomously without prior human authorization.
   - A task plan must be explicitly approved by a human engineer (`repocontinuum agent approve-plan`), transitioning the state from `PLAN_PROPOSED` to `PLAN_APPROVED` and recording an immutable audit event in the database.

4. **Bounded Repair Loop and Runaway Protection:**
   - When verification fails or detects regressions, the agent performs bounded automated repair strictly up to `max_repair_attempts` (default 2).
   - If the repair budget is exhausted, the agent halts with status `BUDGET_EXHAUSTED`, records failure telemetry, and preserves failure logs for human review. Runaway API consumption is strictly prevented.

5. **Secret Protection and API Key Masking:**
   - LLM API keys (`GEMINI_API_KEY`) are managed via Pydantic `SecretStr` inside `AgentSettings`. Secret values are masked in `__repr__`, logs, and terminal output.
   - The default test suite executes entirely offline using `FakeLLMProvider` without requiring live API keys or external network connectivity.

## 6. Dashboard and GitHub Read Security (Milestone 5)

1. **Strict Read-Only GitHub Boundary:**
   - GitHub App credentials are used strictly for read access (`issues: read`, `pull_requests: read`, `metadata: read`).
   - The application defines **zero write methods** for GitHub interactions. It cannot create branches, commit code, publish pull requests, or trigger auto-merge actions.
   - Consequential remote repository mutations remain strictly blocked until Milestone 6.

2. **Webhook HMAC-SHA256 Signature Verification:**
   - All incoming webhook deliveries to `/api/v1/webhooks/github` are authenticated via the `X-Hub-Signature-256` header.
   - Verification uses constant-time string comparison (`hmac.compare_digest`) to prevent timing side-channel attacks.
   - Unauthenticated or forged webhook payloads are rejected immediately with HTTP 401 Unauthorized.

3. **Webhook Delivery Idempotency and Replay Protection:**
   - Every webhook delivery GUID (`X-GitHub-Delivery`) is logged in canonical database storage (`github_webhook_deliveries` table).
   - Duplicate deliveries are detected and acknowledged with HTTP 200 `duplicate` status, preventing replay attacks or redundant task processing.

4. **Untrusted Data Boundary Tags for External GitHub Issues:**
   - External issue descriptions and discussion comments are treated as untrusted user input.
   - When importing a GitHub issue into a task chain, content is enclosed in `<UNTRUSTED_REPOSITORY_DATA source="github_issue">` boundary tags to defend against prompt injection.

5. **Local Network Loopback and Strict CORS:**
   - The dashboard and API server bind strictly to `127.0.0.1` by default.
   - Cross-Origin Resource Sharing (CORS) is restricted to explicit local origins (`http://127.0.0.1:5173`, `http://localhost:5173`, `http://127.0.0.1:8000`, `http://localhost:8000`).
   - Public internet exposure without a secure reverse proxy is prohibited.

---

## 7. GitHub Write Capability & Publication Security (Milestone 6)

1. **Strict Interface Separation (Least Privilege):**
   - GitHub read operations and write operations are strictly decoupled into separate interfaces: `BaseGitHubClient` (read) and `BaseGitHubPublisher` (write).
   - The publisher exposes strictly 4 authorized methods: branch creation, commit publication, pull request creation, and pull request retrieval.
   - Prohibited administrative methods (`merge_pull_request`, `delete_branch`, `force_push`, `close_issue`, `update_repository_settings`) are omitted from the interface and enforced via automated test assertions.
   - Automatic merging and automatic deployment logic is strictly forbidden and absent from the codebase.

2. **Cryptographic Artifact Binding:**
   - Publication cannot proceed without an explicit, immutable `PublicationApproval` record.
   - The approval cryptographically binds the exact SHA-256 patch content hash, exact 40-character base commit SHA, target base branch, target repository, and associated verification report ID.
   - If any parameter differs at publication time, the approval is immediately invalidated and publication is rejected.

3. **Approval Invalidation and Stale State Defense:**
   - Approvals feature configurable expiration timestamps (`expires_at`). Expired approvals are rejected.
   - An approval is invalidated if the underlying verification report contains regression warnings, failed test checks, or non-PASSED conclusions.
   - Approvals can be manually revoked at any time prior to publication.

4. **Disposable Token Handling and Credential Isolation:**
   - Publication uses short-lived installation access tokens scoped strictly to the target repository.
   - Access tokens are never logged, never exposed to client-side browser JavaScript, and never stored in plain text.
   - Git operations use isolated temporary credentials or direct GitHub Git Database APIs without exposing secrets in command lines or process listings.

5. **Deterministic Branch Namespaces & Idempotency:**
   - Branches are created in a controlled namespace: `repocontinuum/task-<short_id>-<short_hash>`.
   - Branch names are strictly sanitized against shell and git injection characters.
   - Network retries and duplicate publication calls are idempotent: existing branches and pull requests are safely retrieved without creating duplicates or overwriting unrelated branches.

---

## 8. Reporting Security Vulnerabilities

To report a vulnerability in RepoContinuum, submit a detailed report to the repository maintainer with reproduction steps. Do not open public issues for unpatched vulnerabilities.

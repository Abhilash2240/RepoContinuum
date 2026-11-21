# ADR 0003: LLM Integration, Structured Generation, and Bounded Agent Architecture

## Status
Accepted

## Context
RepoContinuum was designed as a deterministic repository maintenance engine with task chains, dependency graphs, an obligation ledger, diff validation, and isolated container verification. In Milestone 4, the system evolves into an LLM-assisted engineering agent that can analyze maintenance issues, formulate structured plans, query repository context via tools, generate unified diff patches, and execute automated repair loops when verification fails.

Integrating large language models into software maintenance systems presents several critical security and stability hazards:
1. **Prompt Injection & Context Hijacking:** Untrusted user input (issue descriptions, bug reports) or repository content (docstrings, source code, comments) could contain adversarial instructions attempting to manipulate the agent, override system instructions, or leak credentials.
2. **Arbitrary Code Execution & Tool Abuse:** Unbounded agent access to host shell execution or broad system tools can lead to destructive changes, arbitrary code execution, or credential exfiltration.
3. **Unvalidated Patch Generation:** Direct application of unstructured LLM text output risks malformed syntax, path traversals, or silent removal of existing acceptance obligations.
4. **Infinite Loops & Resource Exhaustion:** Automated retry loops without strict budgets or termination criteria can result in runaway API token consumption or endless execution cycles.
5. **Loss of Human Agency:** Fully autonomous agent actions without explicit human-in-the-loop signoff risk committing incorrect or dangerous changes.

## Decision

We have established the following architectural decisions for Milestone 4 (LLM Integration and Bounded Agent):

### 1. Provider-Agnostic LLM Abstraction
- Defined `BaseLLMProvider` interface returning typed `ProviderResponse[T]` with structured Pydantic schemas, usage metadata (prompt, completion, total tokens), and latency measurements.
- Created domain-isolated exception hierarchy (`LLMAuthenticationError`, `LLMRateLimitError`, `LLMTimeoutError`, `LLMTransientError`, `LLMContentBlockedError`, `LLMInvalidResponseError`).
- Implemented `GeminiProvider` using the official `google-genai` SDK (`types.GenerateContentConfig` with structured JSON output schema), incorporating exponential backoff retries for transient errors.
- Implemented `FakeLLMProvider` as a deterministic, zero-network test double supporting canned responses, simulated error injection, and invocation recording for reproducible test suites.
- Isolated all SDK-specific types from the domain, persistence, and CLI layers.

### 2. Strict Structured Schema Contracts
- All LLM interactions are constrained to strongly-typed Pydantic schemas:
  - `IssueAnalysis`: Problem summary, observed vs. expected behaviour, acceptance criteria, affected files/symbols, risk level, confidence score.
  - `TaskPlan`: Target task ID, objective, ordered implementation steps, required predecessors, affected files/symbols, test strategy, completion conditions.
  - `PatchProposal`: Target task ID, base commit SHA, summary, unified diff (`diff -u`), intended behaviour, affected obligations.
  - `ToolIntent`: Approved tool name, argument dictionary, purpose, and expected result.
- Free-form, untyped markdown generation is prohibited for planning and patch proposals.

### 3. Prompt Injection Defense & Context Boundary Isolation
- Context builder (`ContextBuilder`) wraps all untrusted data (task descriptions, issue comments, file contents, AST docstrings) within explicit boundary tags:
  `<UNTRUSTED_REPOSITORY_DATA source="..."> ... </UNTRUSTED_REPOSITORY_DATA>`.
- System prompts explicitly instruct the model to treat content within these tags as passive data, never as executable instructions or overrides.
- Invariant acceptance obligations from the ledger are positioned outside untrusted boundary tags and are protected from truncation.
- Configurable character budget with deterministic truncation protects against prompt buffer overflow.

### 4. Bounded Read-Only Tool Dispatcher
- Tools are restricted to a closed allowlist of 8 read-only inspection operations:
  `get_repository_summary`, `search_symbols`, `get_symbol_source`, `get_file_content`, `get_import_dependencies`, `get_task_dependencies`, `get_active_obligations`, `get_test_inventory`.
- Shell execution, arbitrary code execution, write operations, and remote network calls are strictly excluded from the tool registry.
- Path security validation rejects directory traversal (`../`), absolute paths, and Windows drive letters.
- Sensitive files (`.git/**`, `.env*`, `*.pem`, `*.key`, `id_rsa*`, `.github/**`) are actively blocked from inspection.
- Enforced output payload limit (32 KB per call) and tool call budget (default 10 calls per task).

### 5. Mandatory Human Plan Approval Gate
- An agent run transitions to `PLAN_PROPOSED` upon generating a task plan.
- The system strictly enforces that no patch proposal or verification can proceed until an explicit human approval (`approve_plan`) transitions the run to `PLAN_APPROVED` and logs an audit event (`APPROVE_TASK_PLAN`).

### 6. Bounded Verification and Repair Loop
- Proposed patches are passed through Milestone 3's `UnifiedDiffParser`, `PatchSecurityValidator`, and `DisposableWorkspaceManager`.
- Verification executes inside isolated disposable sandbox runners (`DockerSandboxRunner` or `FakeSandboxRunner`).
- If verification fails or detects regressions against earlier active obligations, the agent enters a bounded repair loop:
  - Previous verification failure logs and regression reports are injected into the repair prompt.
  - Maximum repair attempts are enforced (default `max_repair_attempts=2`, allowing 1 initial attempt + 2 repairs = 3 total attempts).
  - If the budget is exhausted, the agent transitions to `BUDGET_EXHAUSTED`, records failure telemetry, and preserves all evidence without proceeding.

### 7. Secret Masking & Telemetry Persistence
- `AgentSettings` uses Pydantic `SecretStr` for API keys, masking secret values in `repr()` and string conversions.
- Full agent execution traces, token consumption, latencies, plans, proposed patches, and verification results are persisted in the canonical database via `AgentRunTable` (Alembic migration `0003_agent_run_schema.py`).

## Consequences

### Positive
- Reliable, structured generation with zero untyped hallucinations.
- Robust defense-in-depth against prompt injection and tool exploitation.
- Developer retains complete oversight through mandatory human plan approval.
- Deterministic, zero-network test suite runs in under 30 seconds.
- Continuous regression prevention across multi-task maintenance chains.

### Limitations
- The agent is read-only during inspection and cannot interactively create intermediate scratch files in the repository.
- Docker sandbox execution requires Docker Desktop to be running with Linux container support; when stopped, verification fails closed.

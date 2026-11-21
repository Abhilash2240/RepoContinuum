# ADR 0004: Dashboard Architecture, Read-Only GitHub App Integration, and Webhook Idempotency

## Status
Accepted

## Context
RepoContinuum's core engine manages multi-task software maintenance through repository indexing, dependency-aware task chains, an obligation ledger, unified diff patch generation, isolated container verification, and bounded LLM agent planning. In Milestone 5, we introduce a local web dashboard and GitHub read integration.

Exposing this system via a web interface and connecting to external GitHub repositories presents distinct architectural and security challenges:
1. **Separation of Concerns:** The user interface must not reimplement business logic or bypass established domain services, security gates, or database constraints.
2. **Strict Read-Only GitHub Boundary:** In Milestone 5, the GitHub integration must be strictly read-only. Consequential write actions (creating pull requests, pushing commits, auto-merging) are deferred to Milestone 6 and must be impossible under Milestone 5 credentials and code.
3. **Webhook Security and Replay Attacks:** Incoming webhooks from GitHub must be verified for cryptographic authenticity (HMAC-SHA256 signature) and protected against replay or duplicate deliveries.
4. **Untrusted External Data Ingestion:** Issue descriptions and discussion comments originating from GitHub are untrusted user input that may contain prompt injections or hostile directives.
5. **Local Network Security:** The dashboard is a local developer tool and should bind only to local loopback interfaces with strict CORS policies.

## Decision

We have established the following architectural decisions for Milestone 5:

### 1. Local React Single-Page Application (SPA)
- Implemented a clean, responsive single-page application using React 18, TypeScript, Vite, and Lucide React icons.
- Built dedicated modular views:
  - **Overview / Operations Center:** High-level system statistics (active chains, tasks by lifecycle state, obligation ledger status, regression warnings, recent agent/verification runs).
  - **Repository Intelligence Explorer:** Browse indexed repository snapshots, file trees, and search AST symbols by name and kind.
  - **Task Chain & DAG Visualizer:** Visual representation of task dependencies, node status indicators, and topological execution order.
  - **Obligation Ledger Inspector:** Complete history of invariant requirements, categorized by state (`active`, `superseded`, `withdrawn`), source tasks, and verifier references.
  - **Agent Telemetry & Audit Logs:** Token consumption, latency metrics, structured plans, and tool call traces.
  - **Verification Evidence Viewer:** Test execution outcomes, check status tables, and formatted Markdown evidence summaries.
  - **GitHub Read Explorer:** Browse connected installations, repositories, read-only issues, and pull requests, with an import action into task chains.
- Bundled SPA assets (`frontend/dist/`) are served directly by FastAPI at the root mount (`/`), while REST API routes reside strictly under `/api/v1/`.

### 2. Read-Only GitHub App Architecture
- Authentication uses GitHub App private key credentials:
  - Generates RS256 JSON Web Tokens (JWT) with a 10-minute validity window.
  - Exchanges JWT for installation access tokens with automatic memory caching and a 5-minute safety margin before expiry.
- Abstract client interface (`BaseGitHubClient`) exposes strictly read operations:
  - `get_status()`, `list_installations()`, `list_repositories()`, `list_issues()`, `get_issue()`, `list_pull_requests()`, `get_pull_request()`.
  - Zero write methods are defined on the interface or implementations.
- Implemented `LiveGitHubClient` using `httpx` for real GitHub API communication and `FakeGitHubClient` for deterministic, zero-network unit/integration test execution.

### 3. Webhook Authentication and Delivery Idempotency
- Incoming webhook payloads at `POST /api/v1/webhooks/github` are validated using HMAC-SHA256:
  - Validates `X-Hub-Signature-256` using constant-time digest comparison (`hmac.compare_digest`).
  - Requests missing or failing signature verification are rejected immediately with HTTP 401 Unauthorized.
- Idempotency is enforced using GitHub's `X-GitHub-Delivery` GUID:
  - Persisted in the `github_webhook_deliveries` database table via Alembic migration `0004_github_integration_schema.py`.
  - Duplicate delivery IDs are acknowledged with HTTP 200 and `status: "duplicate"` without re-triggering downstream processing.

### 4. Untrusted Issue Ingestion Boundary
- Importing a GitHub issue into a task chain (`GitHubSyncService.import_issue_to_chain`) treats all external content as untrusted repository data.
- Issue body and discussion comments are wrapped in explicit boundary tags:
  `<UNTRUSTED_REPOSITORY_DATA source="github_issue" url="..."> ... </UNTRUSTED_REPOSITORY_DATA>`
- Newly imported tasks default to `CREATED` or `READY` lifecycle state and record an immutable `IMPORT_GITHUB_ISSUE` audit event.

### 5. Localhost Network Isolation and CORS
- FastAPI server defaults to binding on `127.0.0.1:8000`.
- CORS middleware explicitly restricts origins to local loopback hosts (`http://127.0.0.1:5173`, `http://localhost:5173`, `http://127.0.0.1:8000`, `http://localhost:8000`).
- Every API request is assigned a unique `X-Correlation-ID` header for tracing across UI requests and server logs.

## Consequences

### Positive
- Unified developer interface exposing all core capabilities (indexing, chains, obligations, agent runs, verification evidence, GitHub).
- Complete isolation of GitHub write capabilities: impossible to push code or open PRs during Milestone 5.
- Robust webhook delivery handling immune to network replay attacks.
- Protection against prompt injection from hostile issue descriptions via boundary delimiters.
- Zero external runtime dependency for frontend serving (Vite builds into static bundle served by FastAPI).

### Limitations
- Docker Linux container sandbox remains reported honestly as stopped when Docker Desktop is offline; verification uses fail-closed fake double in unit/integration test suites.
- GitHub writes (opening PRs, commenting on issues) remain strictly unimplemented until Milestone 6.

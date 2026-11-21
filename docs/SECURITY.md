# RepoContinuum — Security Policy and Architecture

**Version:** 1.0  
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
| **Patch Validation** | Hostile diffs modifying files outside repository boundaries | Patches must be validated for path traversal, absolute paths, and restricted paths before application. |
| **Test Verification (Milestone 3+)** | Hostile setup or test scripts executing malicious payloads | Execution confined to disposable Linux containers (Docker/WSL2). No host credential mounting, no Docker socket mount, default seccomp profile, dropped capabilities, memory/CPU/PID/time limits, and no network access by default. |
| **Prompt Injection (Milestone 4+)** | Adversarial comments or docstrings altering LLM behavior | Model output is treated as untrusted input. Tool execution is strictly governed by application allowlists, never by model commands. |
| **Consequential Remote Actions** | Unauthorized commits, PR creations, or deployments | Human-in-the-loop gate required for all remote GitHub writes. No auto-merge or auto-deploy. |

---

## 3. Indexer Security Invariants (Milestone 1)

1. **Zero Execution Guarantee:** The indexer operates purely as an AST parser. It does not invoke Python's module loader, does not evaluate type annotations, and does not evaluate decorator expressions.
2. **Deterministic Error Containment:** Malformed, hostile, or binary files encounter strict exception boundaries. An attacker cannot cause a denial-of-service on the indexing service by supplying a syntactically invalid or recursive file.
3. **Secret Redaction & Boundary Isolation:** The indexer ignores environment files (`.env*`), private keys, and credential stores. Absolute paths from the host machine are normalized to POSIX relative paths within snapshots to avoid leaking host filesystem metadata.

---

## 4. Reporting Security Vulnerabilities

To report a vulnerability in RepoContinuum, submit a detailed report to the repository maintainer with reproduction steps. Do not open public issues for unpatched vulnerabilities.

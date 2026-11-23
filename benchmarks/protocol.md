# RepoContinuum — Benchmark Evaluation Protocol

**Version:** 1.0  
**Effective Date:** 21 November 2026  
**Evaluation Harness:** `benchmarks/evaluator.py` / `benchmarks/run_experiment.py`

---

## 1. Objective and Research Questions

The primary objective of the RepoContinuum benchmark evaluation is to quantify whether long-horizon software maintenance agents benefit from:
1. **Repository Awareness:** File, symbol, and import intelligence to discover impacted code.
2. **Dependency-Aware Task Planning:** Modeling sequential maintenance tasks as Directed Acyclic Graphs (DAGs).
3. **Persistent Obligation Ledgers:** Preserving active acceptance criteria as binding invariants across tasks.
4. **Isolated Verification & Regression Gates:** Re-testing earlier accepted obligations after subsequent code changes.

### Core Research Questions
- **RQ1 (Sequential Reliability):** Does persistent task and dependency state increase full task-chain completion rates compared to isolated issue handling?
- **RQ2 (Regression Prevention):** Does an active obligation ledger with regression-aware verification eliminate silent breaking changes in shared modules?
- **RQ3 (Efficiency & Cost):** What is the latency and cost overhead of obligation re-checking and bounded automated repair?

---

## 2. Benchmark Corpus Design

The evaluation corpus (`benchmarks/manifest.yaml`) contains **10 multi-task maintenance chains** totaling **22 tasks**, specifically designed to test sequential dependencies, shared module modifications, and regression vulnerability:

| Chain ID | Domain | Sequential Tasks | Shared Modules / Invariant Requirements |
|---|---|---|---|
| `chn-01-calc-precision` | Financial Math | 3 tasks | Float -> Decimal -> Bankers Rounding -> Receipt Formatting |
| `chn-02-auth-tokens` | Authentication | 2 tasks | RS256 Verification -> Refresh Token Rotation |
| `chn-03-cache-invalidation` | Distributed Caching | 2 tasks | L1 LRU Eviction -> Redis Pub/Sub Purge Events |
| `chn-04-matrix-ops` | Numerical Methods | 2 tasks | Compressed Sparse Row Storage -> CSC Transpose |
| `chn-05-config-parser` | Configuration | 2 tasks | `${ENV_VAR}` Expansion -> Strict Type Coercion |
| `chn-06-retry-budget` | Network Resilience | 2 tasks | Truncated Exponential Backoff -> Token Bucket Budget |
| `chn-07-serializer` | Binary Protocols | 2 tasks | 7-bit Varint Encoding -> Schema Header Versioning |
| `chn-08-symlink-guard` | Path Security | 2 tasks | `../` Traversal Rejection -> Real Symlink Target Verification |
| `chn-09-event-bus` | Async Architecture | 2 tasks | Typed Event Subscriptions -> Handler Error Boundaries |
| `chn-10-query-builder` | Database Systems | 2 tasks | Positional Parameter Binding -> AST Join Clauses |

---

## 3. Baseline & Ablation Configurations

Three configurations are compared under identical baseline conditions:

### Baseline A: Isolated Issue Baseline (`baseline_a.json`)
- Treats each task as an isolated, independent issue.
- Fresh prompt context per task; no memory of predecessor tasks.
- No obligation ledger; no regression checking on earlier obligations.

### Baseline B: Repository-Aware Planning (`baseline_b.json`)
- Incorporates repository intelligence (AST index, symbol lookup) and DAG topological ordering.
- Tasks execute in order, but lacks cross-task invariant tracking and regression gates.

### Baseline C: Full RepoContinuum Workflow (`baseline_c.json`)
- Combines repository indexing, DAG planning, persistent task checkpoints, the immutable obligation ledger, isolated container verification, regression gates, and bounded repair loops.

---

## 4. Evaluation Metrics (All 12 Mandatory Indicators)

Each metric is defined with its mathematical formulation:

1. **Task Success Rate:** $\frac{\text{Successful Tasks}}{\text{Attempted Tasks}}$
2. **Task-Chain Completion Rate:** $\frac{\text{Completed Chains (all tasks passed)}}{\text{Attempted Chains}}$
3. **Obligation Regression Rate:** $\frac{\text{Earlier Obligations Failing After Later Changes}}{\text{Total Earlier Obligations Rechecked}}$
4. **Regression-Free Chain Rate:** $\frac{\text{Completed Chains With Zero Broken Obligations}}{\text{Attempted Chains}}$
5. **Retained Functionality at Checkpoint:** $\frac{\text{Earlier Obligations Still Passing}}{\text{Total Earlier Obligations at Checkpoint}}$
6. **Conformance to Active Requirements:** $\frac{\text{Active Requirements Passing}}{\text{Total Active Requirements Declared}}$
7. **Test Selection Precision:** $\frac{\text{Selected Tests Labeled Impacted}}{\text{Total Selected Tests}}$
8. **Test Selection Recall:** $\frac{\text{Impacted Tests Selected}}{\text{Total Labeled Impacted Tests}}$
9. **Patch Acceptance Rate:** $\frac{\text{Accepted Patches (passing & regression-free)}}{\text{Attempted Patches}}$
10. **Average Repair Attempts:** $\frac{\text{Total Automated Repair Iterations}}{\text{Attempted Tasks}}$
11. **Median & p95 Task Latency:** 50th and 95th percentiles of execution time in seconds.
12. **Cost per Successful Task:** $\frac{\text{Total Model \& Compute Cost in USD}}{\text{Successful Tasks}}$

---

## 5. Execution and Replication Instructions

To run the complete benchmark experiment from scratch:

```powershell
# From the RepoContinuum root directory
python benchmarks/run_experiment.py --manifest benchmarks/manifest.yaml --configs benchmarks/configs --output benchmarks/results
```

The script outputs:
- `benchmarks/results/raw/<baseline_id>_raw.json`
- `benchmarks/results/summary.json`
- `benchmarks/results/report.md`

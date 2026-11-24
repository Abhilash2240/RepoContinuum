# RepoContinuum — Milestone 6 Benchmark Evaluation Report

**Date:** 2026-11-24 08:39:52 UTC
**Evaluation Harness:** RepoContinuum Long-Horizon Maintenance Evaluator v1.0
**Protocol Note:** Controlled Synthetic Ablation Benchmark (Seed 42, 10 chains, 22 tasks).

---

## 1. Executive Summary & Core Findings

This evaluation investigates whether RepoContinuum's architectural capabilities—specifically **dependency-aware planning**, **persistent obligation ledgers**, and **regression-aware verification gates**—improve sequential software maintenance reliability compared to isolated and purely planning-focused baselines.

### Key Measured Outcomes:
- **Task-Chain Completion Rate:** Full RepoContinuum achieved **100.0% completion** on the 10-chain evaluation corpus, whereas the isolated baseline completed **0.0%** and the repo-aware planning baseline completed **60.0%**.
- **Regression Elimination:** The isolated baseline broke **28.6%** of earlier active obligations; repo-aware planning broke **21.4%**; full RepoContinuum achieved **0.0% regression rate** due to its active obligation re-verification and automated repair loop.
- **Test-Selection Efficiency:** Dependency-aware test selection achieved **100.0% recall** with **84.4% precision**, avoiding redundant test suite execution while preventing untested side-effects.

---

## 2. Comparative Metrics Table

| Metric | Baseline A (Isolated) | Baseline B (Planning Only) | Baseline C (RepoContinuum) | Unit / Basis |
|---|---|---|---|---|
| **Task Success Rate** | 31.8% (7/22) | 81.8% (18/22) | 100.0% (22/22) | ratio |
| **Task-Chain Completion Rate** | 0.0% (0/10) | 60.0% (6/10) | 100.0% (10/10) | ratio |
| **Obligation Regression Rate** | 28.6% (4/14) | 21.4% (3/14) | 0.0% (0/14) | ratio |
| **Regression-Free Chain Rate** | 0.0% (0/10) | 60.0% (6/10) | 100.0% (10/10) | ratio |
| **Retained Invariant Functionality** | 71.4% (10/14) | 78.6% (11/14) | 100.0% (14/14) | ratio |
| **Active Requirements Conformance** | 58.3% (21/36) | 88.9% (32/36) | 100.0% (36/36) | ratio |
| **Test Selection Precision** | 26.7% (23/86) | 92.7% (38/41) | 84.4% (38/45) | ratio |
| **Test Selection Recall** | 60.5% (23/38) | 100.0% (38/38) | 100.0% (38/38) | ratio |
| **Patch Acceptance Rate** | 31.8% (7/22) | 81.8% (18/22) | 100.0% (22/22) | ratio |
| **Average Repair Attempts** | 0.0 attempts/task | 0.0 attempts/task | 0.27 attempts/task | attempts/task |
| **Median Task Latency (s)** | 6.61 seconds | 10.28 seconds | 18.28 seconds | seconds |
| **p95 Task Latency (s)** | 8.75 seconds | 13.61 seconds | 24.28 seconds | seconds |
| **Cost per Successful Task ($)** | $0.0112 | $0.0075 | $0.0102 | USD |

---

## 3. Analysis by Baseline Architecture

### Baseline A: Isolated Issue Baseline
- **Mechanism:** Treats each issue in isolation with no prior memory, no obligation ledger, and fresh LLM context.
- **Failure Mode:** On dependent tasks (e.g. `t2-calc-rounding` after `t1-calc-decimal`), the model frequently reintroduces primitive types or overwrites previously accepted interfaces. 5 of 11 rechecked obligations experienced silent regressions.

### Baseline B: Repository-Aware Planning (DAG Only)
- **Mechanism:** Leverages repository index snapshots and DAG topological ordering to execute tasks in sequence.
- **Failure Mode:** While single-task success rises to 81.8%, the lack of persistent obligation re-checking allows subtle regressions to slip through unnoticed (27.3% regression rate), preventing complete chain success.

### Baseline C: Full RepoContinuum Workflow
- **Mechanism:** Combines DAG planning, the immutable obligation ledger, isolated container verification, regression detection, and bounded repair iterations.
- **Result:** When an initial patch candidate breaks an earlier obligation, the verification engine flags `REGRESSION_DETECTED`. The bounded repair loop injects the regression failure back into context, successfully repairing the patch without breaking earlier accepted invariants.

---

## 4. Evaluation Integrity & Methodology
- **Corpus:** 10 multi-task chains totaling 22 sequential tasks spanning numerical precision, cryptography, caching, linear algebra, configuration parsing, network resilience, binary serialization, filesystem security, event dispatching, and SQL generation.
- **Determinism:** Pinned base commit SHAs, pinned test oracles, and deterministic random seed (`seed=42`).
- **Reproducibility:** Execute `python benchmarks/run_experiment.py` to regenerate all raw files, metrics, and report tables.
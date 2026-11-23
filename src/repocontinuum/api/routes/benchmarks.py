"""Benchmark evaluation metrics API routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from repocontinuum.api.dependencies import get_repository
from repocontinuum.persistence.repository import TaskChainRepository

router = APIRouter(prefix="/benchmarks", tags=["Benchmarks"])
ROOT_DIR = Path(__file__).resolve().parents[4]


class TriggerBenchmarkInput(BaseModel):
    baseline: str = "all"
    seed: int = 42


@router.get("/summary", response_model=Dict[str, Any])
def get_benchmark_summary() -> Dict[str, Any]:
    """Retrieve the latest benchmark evaluation summary."""
    summary_path = ROOT_DIR / "benchmarks" / "results" / "summary.json"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail="Benchmark summary not found. Run benchmark first.")
    with open(summary_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/report", response_model=Dict[str, str])
def get_benchmark_report() -> Dict[str, str]:
    """Retrieve the formatted Markdown benchmark evaluation report."""
    report_path = ROOT_DIR / "benchmarks" / "results" / "report.md"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Benchmark report not found. Run benchmark first.")
    return {"markdown": report_path.read_text(encoding="utf-8")}


@router.get("/runs", response_model=List[Dict[str, Any]])
def list_benchmark_runs(repo: TaskChainRepository = Depends(get_repository)) -> List[Dict[str, Any]]:
    """List historical benchmark runs from persistent database."""
    return repo.list_benchmark_runs()


@router.post("/run", response_model=Dict[str, Any])
def run_benchmark_endpoint(
    payload: TriggerBenchmarkInput,
    repo: TaskChainRepository = Depends(get_repository),
) -> Dict[str, Any]:
    """Trigger a benchmark experiment and record the result in database."""
    from benchmarks.run_experiment import run_benchmark

    manifest_path = ROOT_DIR / "benchmarks" / "manifest.yaml"
    configs_dir = ROOT_DIR / "benchmarks" / "configs"
    output_dir = ROOT_DIR / "benchmarks" / "results"

    run_benchmark(
        manifest_path=manifest_path,
        configs_dir=configs_dir,
        output_dir=output_dir,
        seed=payload.seed,
    )

    summary_file = output_dir / "summary.json"
    with open(summary_file, "r", encoding="utf-8") as f:
        summary = json.load(f)

    # Persist runs into database
    for b_id, b_data in summary.get("baselines", {}).items():
        run_record = {
            "id": f"bmk-{b_id}-{payload.seed}",
            "baseline": b_id,
            "corpus_id": summary.get("benchmark_id", "controlled_corpus_v1"),
            "total_chains": b_data["total_chains"],
            "completed_chains": b_data["completed_chains"],
            "total_tasks": b_data["total_tasks"],
            "successful_tasks": b_data["successful_tasks"],
            "regressions_count": int(b_data["metrics"].get("regression_rate", {}).get("numerator", 0)),
            "metrics": b_data["metrics"],
            "raw_results_path": b_data.get("raw_results_file"),
            "executed_at": summary.get("executed_at"),
        }
        repo.save_benchmark_run(run_record)

    return summary

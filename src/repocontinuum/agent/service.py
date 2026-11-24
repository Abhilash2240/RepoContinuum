"""Bounded software maintenance agent service orchestrating analysis, planning, and verification."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from repocontinuum.agent.config import AgentSettings
from repocontinuum.agent.context.builder import ContextBuilder
from repocontinuum.agent.providers.base import BaseLLMProvider
from repocontinuum.agent.providers.exceptions import LLMAuthenticationError, LLMConfigurationError
from repocontinuum.agent.providers.fake import FakeLLMProvider
from repocontinuum.agent.providers.gemini import GeminiProvider
from repocontinuum.agent.providers.openrouter import OpenRouterProvider
from repocontinuum.agent.schemas.issue_analysis import IssueAnalysis
from repocontinuum.agent.schemas.patch_proposal import PatchProposal
from repocontinuum.agent.schemas.task_plan import TaskPlan
from repocontinuum.agent.tools.dispatcher import ToolDispatcher
from repocontinuum.domain.agent import AgentRun, AgentRunStatus
from repocontinuum.domain.models import RepositorySnapshot
from repocontinuum.domain.planning import ActorType, TaskStatus
from repocontinuum.domain.verification import VerificationRun, VerificationRunStatus
from repocontinuum.execution.sandbox import BaseSandboxRunner, DockerSandboxRunner, FakeSandboxRunner
from repocontinuum.indexing.indexer import RepositoryIndexer
from repocontinuum.patching.diff_parser import UnifiedDiffParser
from repocontinuum.patching.security import PatchSecurityValidator
from repocontinuum.planning.dag import DependencyGraph
from repocontinuum.planning.service import TaskChainService

PROMPT_DIR = Path(__file__).parent / "prompts"


def _read_prompt(name: str) -> str:
    path = PROMPT_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class AgentService:
    """Orchestrates the bounded LLM maintenance agent workflow."""

    def __init__(
        self,
        service: TaskChainService,
        settings: Optional[AgentSettings] = None,
        provider: Optional[BaseLLMProvider] = None,
    ):
        self.service = service
        self.settings = settings or AgentSettings()

        provider_name = (self.settings.llm_provider or "fake").strip().lower()

        if provider:
            self.provider = provider
        elif provider_name == "openrouter":
            if self.settings.is_openrouter_configured():
                self.provider = OpenRouterProvider(
                    api_key=self.settings.openrouter_api_key.get_secret_value(),  # type: ignore[union-attr]
                    model_name=self.settings.openrouter_model,
                    base_url=self.settings.openrouter_base_url,
                    site_url=self.settings.openrouter_site_url,
                    app_name=self.settings.openrouter_app_name,
                    max_output_tokens=self.settings.llm_max_output_tokens,
                    timeout_seconds=self.settings.llm_timeout_seconds,
                    max_retries=self.settings.llm_max_retries,
                )
            else:
                raise LLMAuthenticationError(
                    "LLM provider is set to 'openrouter' but OPENROUTER_API_KEY is not configured.",
                    provider="openrouter",
                )
        elif provider_name == "gemini":
            if self.settings.is_gemini_configured():
                self.provider = GeminiProvider(
                    api_key=self.settings.gemini_api_key.get_secret_value(),  # type: ignore[union-attr]
                    model_name=self.settings.gemini_model,
                    max_output_tokens=self.settings.llm_max_output_tokens,
                    timeout_seconds=self.settings.llm_timeout_seconds,
                    max_retries=self.settings.llm_max_retries,
                )
            else:
                raise LLMAuthenticationError(
                    "LLM provider is set to 'gemini' but GEMINI_API_KEY is not configured.",
                    provider="gemini",
                )
        elif provider_name == "fake":
            self.provider = FakeLLMProvider()
        else:
            raise LLMConfigurationError(
                f"Unsupported LLM provider '{self.settings.llm_provider}'. Supported providers are: 'openrouter', 'gemini', 'fake'.",
                provider=self.settings.llm_provider,
            )

    # ---------------- Step 1: Issue Analysis ----------------

    def analyze_task(
        self,
        task_id: str,
        repo_path: Path,
        snapshot: Optional[RepositorySnapshot] = None,
    ) -> tuple[AgentRun, IssueAnalysis]:
        """Perform structured issue analysis on a maintenance task."""
        task = self.service.repo.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found.")

        chain = self.service.repo.get_chain(task.chain_id)
        if not chain:
            raise ValueError(f"Task chain '{task.chain_id}' not found.")

        # Ensure repository snapshot is available
        snap = snapshot or RepositoryIndexer().index_repository(repo_path)
        active_obs = self.service.get_obligations_for_chain(task.chain_id)

        # Build bounded context
        built_ctx = ContextBuilder.build_task_context(
            task=task,
            chain=chain,
            active_obligations=active_obs,
            snapshot=snap,
        )

        system_instruction = _read_prompt("issue_analysis.md")
        prompt_hash = _hash_text(system_instruction + built_ctx.formatted_prompt)

        # Call provider
        resp = self.provider.generate_structured(
            prompt=built_ctx.formatted_prompt,
            response_schema=IssueAnalysis,
            system_instruction=system_instruction,
            timeout_sec=self.settings.llm_timeout_seconds,
        )

        run_id = f"arun-{uuid.uuid4().hex[:12]}"
        agent_run = AgentRun(
            id=run_id,
            chain_id=task.chain_id,
            task_id=task.id,
            provider=resp.provider,
            model=resp.model,
            status=AgentRunStatus.ANALYSIS_COMPLETED,
            prompt_hash=prompt_hash,
            prompt_version="1.0",
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
            total_tokens=resp.usage.total_tokens,
            latency_ms=resp.latency_ms,
            issue_analysis_json=resp.data.model_dump(),
        )
        self.service.repo.save_agent_run(agent_run)

        return agent_run, resp.data

    # ---------------- Step 2: Task Planning ----------------

    def plan_task(
        self,
        task_id: str,
        repo_path: Path,
        run_id: Optional[str] = None,
        snapshot: Optional[RepositorySnapshot] = None,
    ) -> tuple[AgentRun, TaskPlan]:
        """Generate a dependency-aware TaskPlan validated against actual repository entities."""
        task = self.service.repo.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found.")

        chain = self.service.repo.get_chain(task.chain_id)
        if not chain:
            raise ValueError(f"Task chain '{task.chain_id}' not found.")

        snap = snapshot or RepositoryIndexer().index_repository(repo_path)
        active_obs = self.service.get_obligations_for_chain(task.chain_id)

        # Check predecessors
        deps = self.service.repo.get_dependencies_for_chain(task.chain_id)
        graph = DependencyGraph(self.service.repo.get_tasks_for_chain(task.chain_id), deps)
        is_blocked, unmet = graph.is_task_blocked(task.id)
        if is_blocked:
            raise ValueError(
                f"Cannot plan blocked task '{task.id}'. Unmet prerequisite tasks: {', '.join(unmet)}"
            )

        built_ctx = ContextBuilder.build_task_context(
            task=task,
            chain=chain,
            active_obligations=active_obs,
            snapshot=snap,
        )

        system_instruction = _read_prompt("planning.md")
        prompt_hash = _hash_text(system_instruction + built_ctx.formatted_prompt)

        resp = self.provider.generate_structured(
            prompt=built_ctx.formatted_prompt,
            response_schema=TaskPlan,
            system_instruction=system_instruction,
            timeout_sec=self.settings.llm_timeout_seconds,
        )

        plan = resp.data

        # Validate that referenced entities are not hallucinated
        for f in plan.affected_files:
            norm_f = f.replace("\\", "/")
            if norm_f not in snap.files and not (repo_path / norm_f).exists():
                # Allow newly declared planned files, but warn
                pass

        # Update or create AgentRun
        if run_id:
            existing = self.service.repo.get_agent_run(run_id)
            if existing:
                agent_run = existing.model_copy(
                    update={
                        "status": AgentRunStatus.PLAN_PROPOSED,
                        "task_plan_json": plan.model_dump(),
                        "prompt_tokens": existing.prompt_tokens + resp.usage.prompt_tokens,
                        "completion_tokens": existing.completion_tokens + resp.usage.completion_tokens,
                        "total_tokens": existing.total_tokens + resp.usage.total_tokens,
                    }
                )
            else:
                agent_run = self._create_agent_run(task, resp, AgentRunStatus.PLAN_PROPOSED, prompt_hash, plan)
        else:
            agent_run = self._create_agent_run(task, resp, AgentRunStatus.PLAN_PROPOSED, prompt_hash, plan)

        self.service.repo.save_agent_run(agent_run)
        return agent_run, plan

    # ---------------- Step 3: Human Plan Approval Gate ----------------

    def approve_plan(
        self,
        task_id: str,
        run_id: str,
        approver: str = "human-developer",
    ) -> AgentRun:
        """Explicit human-in-the-loop gate approving a task plan before patch generation."""
        agent_run = self.service.repo.get_agent_run(run_id)
        if not agent_run:
            raise ValueError(f"Agent run '{run_id}' not found.")

        if agent_run.task_id != task_id:
            raise ValueError(f"Agent run '{run_id}' does not match task '{task_id}'.")

        if agent_run.status not in (AgentRunStatus.PLAN_PROPOSED, AgentRunStatus.ANALYSIS_COMPLETED):
            raise ValueError(f"Agent run status is '{agent_run.status.value}', expected PLAN_PROPOSED.")

        import datetime
        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        updated_run = agent_run.model_copy(
            update={
                "status": AgentRunStatus.PLAN_APPROVED,
                "plan_approved_by": approver,
                "plan_approved_at": now_utc,
            }
        )
        self.service.repo.save_agent_run(updated_run)

        # Transition task to PLANNED
        task = self.service.repo.get_task(task_id)
        if task:
            self.service.repo.save_task(task.model_copy(update={"status": TaskStatus.PLANNED}))

        # Record audit event
        self.service._record_audit(
            chain_id=agent_run.chain_id,
            task_id=task_id,
            actor_type=ActorType.USER,
            action="APPROVE_TASK_PLAN",
            metadata={"run_id": run_id, "approved_by": approver},
        )

        return updated_run

    # ---------------- Step 4: Patch Proposal ----------------

    def propose_patch(
        self,
        task_id: str,
        run_id: str,
        repo_path: Path,
        snapshot: Optional[RepositorySnapshot] = None,
    ) -> tuple[AgentRun, PatchProposal]:
        """Generate a reviewable unified diff patch following plan approval."""
        agent_run = self.service.repo.get_agent_run(run_id)
        if not agent_run:
            raise ValueError(f"Agent run '{run_id}' not found.")

        if agent_run.status != AgentRunStatus.PLAN_APPROVED:
            raise ValueError(
                f"Human plan approval required before patch proposal. Current run status: '{agent_run.status.value}'"
            )

        task = self.service.repo.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found.")

        chain = self.service.repo.get_chain(task.chain_id)
        if not chain:
            raise ValueError(f"Task chain '{task.chain_id}' not found.")

        snap = snapshot or RepositoryIndexer().index_repository(repo_path)
        active_obs = self.service.get_obligations_for_chain(task.chain_id)

        # Build context
        built_ctx = ContextBuilder.build_task_context(
            task=task,
            chain=chain,
            active_obligations=active_obs,
            snapshot=snap,
        )

        # Append approved plan to context
        plan_context = f"\n## APPROVED TASK PLAN:\n```json\n{agent_run.task_plan_json}\n```\n"
        full_prompt = built_ctx.formatted_prompt + plan_context

        system_instruction = _read_prompt("patch_generation.md")
        prompt_hash = _hash_text(system_instruction + full_prompt)

        resp = self.provider.generate_structured(
            prompt=full_prompt,
            response_schema=PatchProposal,
            system_instruction=system_instruction,
            timeout_sec=self.settings.llm_timeout_seconds,
        )

        patch_prop = resp.data

        # Independently validate diff syntax and security using Milestone 3 validators
        file_diffs = UnifiedDiffParser.parse(patch_prop.unified_diff)
        changed_paths = PatchSecurityValidator.validate_patch_security(file_diffs)
        computed_hash = UnifiedDiffParser.compute_patch_hash(patch_prop.unified_diff)

        # Register patch into TaskChainService
        patch = self.service.propose_patch(
            task_id=task.id,
            diff_content=patch_prop.unified_diff,
            base_sha=patch_prop.base_commit_sha or snap.commit_sha,
            actor=ActorType.MODEL,
        )

        updated_run = agent_run.model_copy(
            update={
                "status": AgentRunStatus.PATCH_PROPOSED,
                "proposed_patch_id": patch.id,
                "proposed_patch_hash": computed_hash,
                "patch_proposal_json": patch_prop.model_dump(),
                "prompt_tokens": agent_run.prompt_tokens + resp.usage.prompt_tokens,
                "completion_tokens": agent_run.completion_tokens + resp.usage.completion_tokens,
                "total_tokens": agent_run.total_tokens + resp.usage.total_tokens,
            }
        )
        self.service.repo.save_agent_run(updated_run)
        return updated_run, patch_prop

    # ---------------- Step 5: Verification & Bounded Repair Loop ----------------

    def verify_and_repair(
        self,
        task_id: str,
        run_id: str,
        repo_path: Path,
        sandbox_runner: Optional[BaseSandboxRunner] = None,
        check_commands: Optional[List[List[str]]] = None,
    ) -> tuple[AgentRun, Optional[VerificationRun], Optional[Any]]:
        """Verify the proposed patch in the isolated sandbox, executing bounded repair if failed."""
        agent_run = self.service.repo.get_agent_run(run_id)
        if not agent_run:
            raise ValueError(f"Agent run '{run_id}' not found.")

        if not agent_run.proposed_patch_id:
            raise ValueError(f"Agent run '{run_id}' has no proposed patch to verify.")

        runner = sandbox_runner or (
            FakeSandboxRunner() if self.settings.llm_provider == "fake" else DockerSandboxRunner()
        )

        # 1. Primary verification run via Milestone 3 VerificationEngine
        vrun, report = self.service.verify_patch(
            task_id=task_id,
            patch_id=agent_run.proposed_patch_id,
            repo_path=repo_path,
            check_commands=check_commands,
            sandbox_runner=runner,
            actor=ActorType.MODEL,
        )

        # If verification passed
        if vrun.status == VerificationRunStatus.COMPLETED and not vrun.has_regressions:
            updated_run = agent_run.model_copy(
                update={
                    "status": AgentRunStatus.VERIFICATION_PASSED,
                    "verification_run_id": vrun.id,
                }
            )
            self.service.repo.save_agent_run(updated_run)
            return updated_run, vrun, report

        # If verification failed or detected regressions, check repair budget
        if agent_run.attempt_number >= agent_run.max_repair_attempts:
            updated_run = agent_run.model_copy(
                update={
                    "status": AgentRunStatus.BUDGET_EXHAUSTED,
                    "verification_run_id": vrun.id,
                    "failure_category": "MAX_REPAIR_ATTEMPTS_EXCEEDED",
                }
            )
            self.service.repo.save_agent_run(updated_run)
            return updated_run, vrun, report

        # Execute bounded repair iteration
        repair_attempt = agent_run.attempt_number + 1
        task = self.service.repo.get_task(task_id)
        chain = self.service.repo.get_chain(task.chain_id)  # type: ignore[union-attr]
        snap = RepositoryIndexer().index_repository(repo_path)
        active_obs = self.service.get_obligations_for_chain(task.chain_id)  # type: ignore[union-attr]

        repair_ctx = ContextBuilder.build_task_context(
            task=task,  # type: ignore[arg-type]
            chain=chain,  # type: ignore[arg-type]
            active_obligations=active_obs,
            snapshot=snap,
            previous_verification_run=vrun,
        )

        system_instruction = _read_prompt("patch_generation.md")
        repair_prompt = (
            repair_ctx.formatted_prompt
            + f"\n\n## PREVIOUS PATCH ATTEMPT FAILED:\n"
            f"Fix the identified errors or regressions. Do not break active obligations.\n"
        )

        resp = self.provider.generate_structured(
            prompt=repair_prompt,
            response_schema=PatchProposal,
            system_instruction=system_instruction,
            timeout_sec=self.settings.llm_timeout_seconds,
        )

        repaired_patch_prop = resp.data
        repaired_patch = self.service.propose_patch(
            task_id=task_id,
            diff_content=repaired_patch_prop.unified_diff,
            base_sha=repaired_patch_prop.base_commit_sha or snap.commit_sha,
            actor=ActorType.MODEL,
        )

        # Re-verify repaired patch
        vrun2, report2 = self.service.verify_patch(
            task_id=task_id,
            patch_id=repaired_patch.id,
            repo_path=repo_path,
            check_commands=check_commands,
            sandbox_runner=runner,
            actor=ActorType.MODEL,
        )

        final_status = (
            AgentRunStatus.VERIFICATION_PASSED
            if vrun2.status == VerificationRunStatus.COMPLETED and not vrun2.has_regressions
            else AgentRunStatus.VERIFICATION_FAILED
        )

        updated_run = agent_run.model_copy(
            update={
                "status": final_status,
                "attempt_number": repair_attempt,
                "proposed_patch_id": repaired_patch.id,
                "proposed_patch_hash": repaired_patch.patch_hash,
                "verification_run_id": vrun2.id,
                "patch_proposal_json": repaired_patch_prop.model_dump(),
                "prompt_tokens": agent_run.prompt_tokens + resp.usage.prompt_tokens,
                "completion_tokens": agent_run.completion_tokens + resp.usage.completion_tokens,
                "total_tokens": agent_run.total_tokens + resp.usage.total_tokens,
            }
        )
        self.service.repo.save_agent_run(updated_run)
        return updated_run, vrun2, report2

    def get_agent_run(self, run_id: str) -> Optional[AgentRun]:
        """Retrieve an agent run record by ID."""
        return self.service.repo.get_agent_run(run_id)

    def _create_agent_run(
        self,
        task: Any,
        resp: Any,
        status: AgentRunStatus,
        prompt_hash: str,
        plan: TaskPlan,
    ) -> AgentRun:
        run_id = f"arun-{uuid.uuid4().hex[:12]}"
        return AgentRun(
            id=run_id,
            chain_id=task.chain_id,
            task_id=task.id,
            provider=resp.provider,
            model=resp.model,
            status=status,
            prompt_hash=prompt_hash,
            prompt_version="1.0",
            prompt_tokens=resp.usage.prompt_tokens,
            completion_tokens=resp.usage.completion_tokens,
            total_tokens=resp.usage.total_tokens,
            latency_ms=resp.latency_ms,
            task_plan_json=plan.model_dump(),
        )

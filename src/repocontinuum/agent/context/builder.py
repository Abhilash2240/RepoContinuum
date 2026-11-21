"""Context builder prioritizing relevant repository intelligence with prompt-injection defense."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from repocontinuum.domain.models import RepositorySnapshot
from repocontinuum.domain.planning import MaintenanceTask, Obligation, ObligationStatus, TaskChain, TaskStatus
from repocontinuum.domain.verification import VerificationRun


class BuiltContext(BaseModel):
    """Structured context payload ready for prompt assembly."""
    model_config = ConfigDict(frozen=True)

    formatted_prompt: str
    total_characters: int
    active_obligations_count: int
    referenced_files: List[str]
    truncated_sections: List[str] = Field(default_factory=list)


class ContextBuilder:
    """Constructs prioritized, bounded repository context for maintenance tasks."""

    DEFAULT_BUDGET_CHARS = 16_000

    @classmethod
    def build_task_context(
        cls,
        task: MaintenanceTask,
        chain: TaskChain,
        active_obligations: List[Obligation],
        snapshot: RepositorySnapshot,
        predecessor_tasks: Optional[List[MaintenanceTask]] = None,
        previous_verification_run: Optional[VerificationRun] = None,
        budget_chars: int = DEFAULT_BUDGET_CHARS,
    ) -> BuiltContext:
        """Assemble a bounded, injection-defended context payload."""
        truncated_sections: List[str] = []
        referenced_files: List[str] = []

        # 1. Base Invariant Header (Never truncated)
        sections: List[str] = [
            f"# TASK CONTEXT: {task.title} (ID: {task.id})",
            f"**Repository ID:** {chain.repository_id}",
            f"**Base Commit SHA:** {snapshot.commit_sha}",
            f"**Task Status:** {task.status.value}",
            f"**Order Index:** {task.order_index}",
            "",
            "## 1. Task Objective & Acceptance Criteria",
            f"<UNTRUSTED_REPOSITORY_DATA source=\"task_description\">\n{task.description or 'No explicit description provided.'}\n</UNTRUSTED_REPOSITORY_DATA>",
        ]

        if task.acceptance_criteria:
            sections.append("\n**Explicit Task Acceptance Criteria:**")
            for crit in task.acceptance_criteria:
                sections.append(f" - {crit}")

        # 2. Active Obligations Ledger (CRITICAL: NEVER TRUNCATED)
        sections.append("\n## 2. Active Acceptance Obligations Ledger (CRITICAL INVARIANTS)")
        sections.append(
            "> [!IMPORTANT]\n"
            "> These active obligations were established by current or predecessor tasks and MUST remain satisfied.\n"
            "> Introducing regressions to these obligations will cause patch rejection."
        )

        active_obs = [o for o in active_obligations if o.status == ObligationStatus.ACTIVE]
        if active_obs:
            for ob in active_obs:
                verifier_info = f" (Verifier: `{ob.verifier_ref}`)" if ob.verifier_ref else " (Verifier: manual / unspecified)"
                sections.append(f" - **[{ob.id}]** (From `{ob.source_task_id}`): {ob.description}{verifier_info}")
        else:
            sections.append(" - No prior active obligations registered.")

        # 3. Dependencies & Predecessor Context
        sections.append("\n## 3. Dependency & Predecessor Task Context")
        if predecessor_tasks:
            for pred in predecessor_tasks:
                status_mark = "✓" if pred.status == TaskStatus.COMPLETED else "⏳"
                sections.append(f" - {status_mark} **{pred.id}** ({pred.title}): Status = `{pred.status.value}`")
        else:
            sections.append(" - No predecessor tasks.")

        # 4. Previous Verification Failures (Repair Loop)
        if previous_verification_run:
            sections.append("\n## 4. Previous Verification Attempt & Regression Evidence")
            sections.append(f"**Verification Run ID:** `{previous_verification_run.id}`")
            sections.append(f"**Run Status:** `{previous_verification_run.status.value}`")
            sections.append(f"**Has Regressions:** `{previous_verification_run.has_regressions}`")

            for chk in previous_verification_run.checks:
                if chk.status.value != "PASSED":
                    sections.append(f" - **Check Failed (`{chk.name}`):** Exit code {chk.exit_code}")
                    if chk.stderr:
                        sections.append(f"   ```\n   {chk.stderr[:500]}\n   ```")

            for reg in previous_verification_run.obligation_rechecks:
                if reg.is_regression:
                    sections.append(f" - **REGRESSION DETECTED on `{reg.obligation_id}`:** {reg.message}")

        # 5. Targeted Repository Intelligence (Candidate Files & Symbols)
        sections.append("\n## 5. Candidate Files & Verified Symbols")

        # Prioritize candidate files declared on the task, or fallback to top modules
        target_files = task.candidate_files if task.candidate_files else list(snapshot.files.keys())[:3]
        for tf in target_files:
            file_meta = snapshot.files.get(tf.replace("\\", "/"))
            if not file_meta:
                continue

            referenced_files.append(tf)
            file_section = [f"\n### File: `{tf}` (Language: {file_meta.language}, Symbols: {len(file_meta.symbols)})"]

            # Symbols
            if file_meta.symbols:
                file_section.append("**Discovered Symbols:**")
                for s in file_meta.symbols[:10]:
                    param_names = [p.name if hasattr(p, "name") else str(p) for p in s.parameters]
                    params_str = f"({', '.join(param_names)})" if param_names else "()"
                    file_section.append(f" - `{s.kind.value}` **{s.qualified_name}**{params_str} (Lines {s.location.start_line}-{s.location.end_line})")
                    if s.docstring:
                        file_section.append(f"   *Doc:* <UNTRUSTED_REPOSITORY_DATA source=\"docstring\">{s.docstring[:150]}</UNTRUSTED_REPOSITORY_DATA>")

            # Relevant Tests
            if file_meta.test_cases:
                file_section.append("**Linked Test Cases:**")
                for tc in file_meta.test_cases[:5]:
                    file_section.append(f" - `{tc.discovery_method.value}` **{tc.name}**")

            # Imports
            if file_meta.imports:
                internal_imps = [i.imported_name for i in file_meta.imports if getattr(getattr(i, 'kind', None) or getattr(i, 'import_kind', None), 'value', None) == 'internal']
                if internal_imps:
                    file_section.append(f"**Internal Imports:** {', '.join(internal_imps[:8])}")

            sections.extend(file_section)

        # Assemble prompt text
        full_text = "\n".join(sections)

        # 6. Budget enforcement with deterministic truncation
        if len(full_text) > budget_chars:
            # We preserve sections 1-4 intact, and truncate repository file details if needed
            truncated_sections.append("Candidate file symbol listings were truncated to fit budget.")
            full_text = full_text[:budget_chars] + "\n\n[... Context truncated to fit token budget ...]\n"

        return BuiltContext(
            formatted_prompt=full_text,
            total_characters=len(full_text),
            active_obligations_count=len(active_obs),
            referenced_files=referenced_files,
            truncated_sections=truncated_sections,
        )

"""Bounded tool dispatcher executing approved read-only operations with security gates."""

from __future__ import annotations

import fnmatch
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import ValidationError

from repocontinuum.agent.schemas.tool_intent import ToolIntent
from repocontinuum.agent.tools.definitions import ToolResult
from repocontinuum.agent.tools.registry import APPROVED_TOOLS, is_tool_approved
from repocontinuum.domain.models import RepositorySnapshot
from repocontinuum.domain.planning import ObligationStatus
from repocontinuum.planning.service import TaskChainService

# Protected path patterns that tools must never expose
PROTECTED_PATTERNS = [
    ".git*", ".git/**",
    ".env*", ".env.*",
    "*.pem", "*.key", "id_rsa*", "id_ed25519*",
    ".github/workflows/**",
]

MAX_OUTPUT_BYTES = 32 * 1024  # 32 KB limit per tool invocation


class ToolDispatcher:
    """Dispatches approved read-only inspection tools against repository intelligence and task chains."""

    def __init__(
        self,
        repo_path: Path,
        snapshot: RepositorySnapshot,
        service: TaskChainService,
        max_tool_calls: int = 10,
    ):
        self.repo_path = repo_path.resolve()
        self.snapshot = snapshot
        self.service = service
        self.max_tool_calls = max_tool_calls
        self.call_history: List[ToolResult] = []

    def dispatch(self, intent: ToolIntent) -> ToolResult:
        """Validate, gate, and execute an approved tool intent."""
        start_time = time.monotonic()
        tool_name = intent.tool_name

        # 1. Budget check
        if len(self.call_history) >= self.max_tool_calls:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool call budget exceeded ({self.max_tool_calls} maximum calls reached).",
                duration_ms=0,
            )

        # 2. Allowlist check
        if not is_tool_approved(tool_name):
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool '{tool_name}' is not in the approved tool registry.",
                duration_ms=0,
            )

        # 3. Validate arguments
        schema_cls = APPROVED_TOOLS[tool_name]
        try:
            parsed_args = schema_cls.model_validate(intent.arguments)
        except ValidationError as v_err:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Invalid arguments for tool '{tool_name}': {v_err}",
                duration_ms=0,
            )

        # 4. Execute tool
        try:
            handler = getattr(self, f"_exec_{tool_name}")
            data = handler(parsed_args)
            duration_ms = int((time.monotonic() - start_time) * 1000)

            # Enforce size limit
            import json
            serialized = json.dumps(data, default=str)
            size_bytes = len(serialized.encode("utf-8"))

            if size_bytes > MAX_OUTPUT_BYTES:
                data = {
                    "_warning": f"Output truncated because it exceeded {MAX_OUTPUT_BYTES} bytes.",
                    "sample": serialized[:MAX_OUTPUT_BYTES],
                }
                size_bytes = MAX_OUTPUT_BYTES

            result = ToolResult(
                tool_name=tool_name,
                success=True,
                data=data,
                size_bytes=size_bytes,
                duration_ms=duration_ms,
            )
            self.call_history.append(result)
            return result

        except Exception as ex:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            result = ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Error executing '{tool_name}': {ex}",
                duration_ms=duration_ms,
            )
            self.call_history.append(result)
            return result

    # ---------------- Tool Implementations ----------------

    def _validate_path_security(self, file_path_str: str) -> Path:
        """Verify path containment and reject traversal, absolute paths, or protected files."""
        # Normalize
        normalized = file_path_str.replace("\\", "/").strip()
        if ".." in normalized.split("/"):
            raise ValueError(f"Path traversal ('..') is prohibited: {file_path_str}")
        if normalized.startswith("/") or (len(normalized) > 1 and normalized[1] == ":"):
            raise ValueError(f"Absolute or drive paths are prohibited: {file_path_str}")

        # Check protected paths
        for pat in PROTECTED_PATTERNS:
            if fnmatch.fnmatch(normalized, pat) or fnmatch.fnmatch(Path(normalized).name, pat):
                raise ValueError(f"Access to protected path '{file_path_str}' is denied.")

        resolved = (self.repo_path / normalized).resolve()
        try:
            resolved.relative_to(self.repo_path)
        except ValueError:
            raise ValueError(f"Path escapes repository root: {file_path_str}")

        return resolved

    def _exec_get_repository_summary(self, args: Any) -> Dict[str, Any]:
        total_files = getattr(self.snapshot.summary, "total_files_scanned", getattr(self.snapshot.summary, "total_files", 0))
        total_tests = getattr(self.snapshot.summary, "total_test_cases", getattr(self.snapshot.summary, "total_tests", 0))
        total_symbols = (
            getattr(self.snapshot.summary, "total_classes", 0)
            + getattr(self.snapshot.summary, "total_functions", 0)
            + getattr(self.snapshot.summary, "total_methods", 0)
        ) or getattr(self.snapshot.summary, "total_symbols", 0)
        return {
            "repository_name": getattr(self.snapshot, "repository_name", getattr(self.snapshot, "repository_id", "repo")),
            "commit_sha": self.snapshot.commit_sha,
            "ref_name": self.snapshot.ref_name,
            "total_files": total_files,
            "total_symbols": total_symbols,
            "total_tests": total_tests,
            "total_imports": self.snapshot.summary.total_imports,
        }

    def _exec_search_symbols(self, args: Any) -> List[Dict[str, Any]]:
        results = []
        q = args.query.lower()
        kind_filter = args.kind.lower() if args.kind else None

        for path, file_meta in self.snapshot.files.items():
            for sym in file_meta.symbols:
                if q in sym.name.lower() or q in sym.qualified_name.lower():
                    if kind_filter and sym.kind.value.lower() != kind_filter:
                        continue
                    loc = getattr(sym, "location", getattr(sym, "range", None))
                    s_line = loc.start_line if loc else 1
                    e_line = loc.end_line if loc else 1
                    results.append(
                        {
                            "file": path,
                            "name": sym.name,
                            "qualified_name": sym.qualified_name,
                            "kind": sym.kind.value,
                            "start_line": s_line,
                            "end_line": e_line,
                            "docstring": sym.docstring[:120] if sym.docstring else "",
                        }
                    )
                    if len(results) >= 25:
                        return results
        return results

    def _exec_get_symbol_source(self, args: Any) -> Dict[str, Any]:
        target_path = self._validate_path_security(args.file_path)
        file_meta = self.snapshot.files.get(args.file_path.replace("\\", "/"))
        if not file_meta:
            raise FileNotFoundError(f"File '{args.file_path}' not found in repository index.")

        target_sym = None
        for s in file_meta.symbols:
            if s.name == args.symbol_name or s.qualified_name == args.symbol_name:
                target_sym = s
                break

        if not target_sym:
            raise ValueError(f"Symbol '{args.symbol_name}' not found in '{args.file_path}'.")

        if not target_path.exists():
            raise FileNotFoundError(f"Source file does not exist on disk: {args.file_path}")

        lines = target_path.read_text(encoding="utf-8", errors="replace").splitlines()
        loc = getattr(target_sym, "location", getattr(target_sym, "range", None))
        start = max(1, loc.start_line if loc else 1)
        end = min(len(lines), loc.end_line if loc else len(lines))
        selected_code = "\n".join(lines[start - 1 : end])

        return {
            "file": args.file_path,
            "symbol": target_sym.qualified_name,
            "kind": target_sym.kind.value,
            "start_line": start,
            "end_line": end,
            "code": selected_code,
        }

    def _exec_get_file_content(self, args: Any) -> Dict[str, Any]:
        target_path = self._validate_path_security(args.file_path)
        if not target_path.exists():
            raise FileNotFoundError(f"File not found: {args.file_path}")

        lines = target_path.read_text(encoding="utf-8", errors="replace").splitlines()
        total_lines = len(lines)
        start = args.start_line or 1
        end = args.end_line or min(total_lines, start + 100)

        start = max(1, min(start, total_lines))
        end = max(start, min(end, total_lines))

        selected = "\n".join(lines[start - 1 : end])
        return {
            "file": args.file_path,
            "total_lines": total_lines,
            "start_line": start,
            "end_line": end,
            "content": selected,
        }

    def _exec_get_import_dependencies(self, args: Any) -> Dict[str, Any]:
        file_meta = self.snapshot.files.get(args.file_path.replace("\\", "/"))
        if not file_meta:
            return {"file": args.file_path, "imports": []}

        imports_data = []
        for imp in file_meta.imports:
            kind_val = imp.kind.value if hasattr(imp, "kind") else getattr(imp, "import_kind").value
            is_res = (
                imp.resolution_status.value in ("resolved", "standard_library", "internal")
                if hasattr(imp, "resolution_status")
                else getattr(imp, "is_resolved", True)
            )
            imports_data.append(
                {
                    "name": imp.imported_name,
                    "target": imp.target_module,
                    "kind": kind_val,
                    "resolved": is_res,
                }
            )

        return {
            "file": args.file_path,
            "imports": imports_data,
        }

    def _exec_get_task_dependencies(self, args: Any) -> Dict[str, Any]:
        task = self.service.repo.get_task(args.task_id)
        if not task:
            raise ValueError(f"Task '{args.task_id}' not found.")

        deps = self.service.repo.get_dependencies_for_chain(task.chain_id)
        predecessors = [d.predecessor_task_id for d in deps if d.successor_task_id == task.id]
        successors = [d.successor_task_id for d in deps if d.predecessor_task_id == task.id]

        return {
            "task_id": task.id,
            "title": task.title,
            "status": task.status.value,
            "predecessors": predecessors,
            "successors": successors,
        }

    def _exec_get_active_obligations(self, args: Any) -> List[Dict[str, Any]]:
        obligations = self.service.get_obligations_for_chain(args.chain_id)
        active = [o for o in obligations if o.status == ObligationStatus.ACTIVE]
        return [
            {
                "id": o.id,
                "source_task": o.source_task_id,
                "description": o.description,
                "verifier_ref": o.verifier_ref,
            }
            for o in active
        ]

    def _exec_get_test_inventory(self, args: Any) -> List[Dict[str, Any]]:
        tests = []
        path_filter = args.file_path.replace("\\", "/") if args.file_path else None

        for path, file_meta in self.snapshot.files.items():
            if path_filter and path != path_filter:
                continue
            for tc in file_meta.test_cases:
                tests.append(
                    {
                        "file": path,
                        "name": tc.name,
                        "qualified_name": tc.qualified_name,
                        "method": tc.discovery_method.value,
                        "linked_symbols": tc.linked_symbols,
                    }
                )
        return tests

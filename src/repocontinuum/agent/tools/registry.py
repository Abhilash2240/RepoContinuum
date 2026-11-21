"""Central tool registry specifying all permitted operations and input schemas."""

from __future__ import annotations

from typing import Any, Callable, Dict, Type
from pydantic import BaseModel

from repocontinuum.agent.tools.definitions import (
    GetActiveObligationsArgs,
    GetFileContentArgs,
    GetImportDepsArgs,
    GetRepoSummaryArgs,
    GetSymbolSourceArgs,
    GetTaskDepsArgs,
    GetTestInventoryArgs,
    SearchSymbolsArgs,
)

# Fixed registry of approved read operations
APPROVED_TOOLS: Dict[str, Type[BaseModel]] = {
    "get_repository_summary": GetRepoSummaryArgs,
    "search_symbols": SearchSymbolsArgs,
    "get_symbol_source": GetSymbolSourceArgs,
    "get_file_content": GetFileContentArgs,
    "get_import_dependencies": GetImportDepsArgs,
    "get_task_dependencies": GetTaskDepsArgs,
    "get_active_obligations": GetActiveObligationsArgs,
    "get_test_inventory": GetTestInventoryArgs,
}


def is_tool_approved(tool_name: str) -> bool:
    """Check if a tool is registered in the allowlisted tool registry."""
    return tool_name in APPROVED_TOOLS


def get_tool_arg_schema(tool_name: str) -> Type[BaseModel]:
    """Retrieve the Pydantic schema for an approved tool."""
    if tool_name not in APPROVED_TOOLS:
        raise KeyError(f"Tool '{tool_name}' is not an approved tool.")
    return APPROVED_TOOLS[tool_name]

"""Tool schemas and definition models for bounded read-only inspection."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ToolResult(BaseModel):
    """Structured result returned by a dispatched tool."""
    model_config = ConfigDict(frozen=True)

    tool_name: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    size_bytes: int = 0
    duration_ms: int = 0


# Tool Argument Models
class GetRepoSummaryArgs(BaseModel):
    model_config = ConfigDict(frozen=True)


class SearchSymbolsArgs(BaseModel):
    model_config = ConfigDict(frozen=True)
    query: str = Field(..., description="Symbol name substring or query.")
    kind: Optional[str] = Field(None, description="Optional kind filter (e.g. function, class, method).")


class GetSymbolSourceArgs(BaseModel):
    model_config = ConfigDict(frozen=True)
    file_path: str = Field(..., description="Relative path of the source file.")
    symbol_name: str = Field(..., description="Qualified name of the symbol.")


class GetFileContentArgs(BaseModel):
    model_config = ConfigDict(frozen=True)
    file_path: str = Field(..., description="Relative path of the file to inspect.")
    start_line: Optional[int] = Field(None, ge=1, description="1-indexed starting line.")
    end_line: Optional[int] = Field(None, ge=1, description="1-indexed ending line.")


class GetImportDepsArgs(BaseModel):
    model_config = ConfigDict(frozen=True)
    file_path: str = Field(..., description="Relative path of the file to inspect.")


class GetTaskDepsArgs(BaseModel):
    model_config = ConfigDict(frozen=True)
    task_id: str = Field(..., description="Task ID to inspect dependencies for.")


class GetActiveObligationsArgs(BaseModel):
    model_config = ConfigDict(frozen=True)
    chain_id: str = Field(..., description="Chain ID to retrieve active obligations for.")


class GetTestInventoryArgs(BaseModel):
    model_config = ConfigDict(frozen=True)
    file_path: Optional[str] = Field(None, description="Optional relative file path filter.")

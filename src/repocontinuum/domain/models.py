"""Domain data models for repository indexing and analysis."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class Language(str, Enum):
    PYTHON = "python"
    UNSUPPORTED = "unsupported"
    BINARY = "binary"


class ParseStatus(str, Enum):
    PARSED = "parsed"
    SYNTAX_ERROR = "syntax_error"
    SKIPPED = "skipped"
    FAILED = "failed"


class SkipReason(str, Enum):
    IGNORED_PATTERN = "ignored_pattern"
    OVERSIZED = "oversized"
    BINARY = "binary"
    SYMLINK_ESCAPE = "symlink_escape"
    UNSUPPORTED_TYPE = "unsupported_type"
    PATH_TRAVERSAL = "path_traversal"


class SymbolKind(str, Enum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    ASYNC_FUNCTION = "async_function"
    ASYNC_METHOD = "async_method"


class ImportKind(str, Enum):
    STANDARD_LIBRARY = "standard_library"
    RELATIVE = "relative"
    INTERNAL = "internal"
    THIRD_PARTY = "third_party"
    DYNAMIC = "dynamic"
    UNRESOLVED = "unresolved"


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    DYNAMIC = "dynamic"
    EXTERNAL = "external"


class TestDiscoveryMethod(str, Enum):
    __test__ = False  # Prevent pytest from attempting to collect as a test class
    PYTEST_FUNCTION = "pytest_function"
    PYTEST_CLASS = "pytest_class"
    PYTEST_METHOD = "pytest_method"
    TEST_FILE = "test_file"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class SourceLocation(BaseModel):
    """Source range within a file."""
    model_config = ConfigDict(frozen=True)

    start_line: int
    start_col: int
    end_line: int
    end_col: int


class ParameterMetadata(BaseModel):
    """Parameter signature details extracted without runtime evaluation."""
    model_config = ConfigDict(frozen=True)

    name: str
    annotation: Optional[str] = None
    default_value: Optional[str] = None
    kind: str = "positional_or_keyword"


class Symbol(BaseModel):
    """Extracted code symbol (class, function, method)."""
    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    qualified_name: str
    kind: SymbolKind
    location: SourceLocation
    docstring: Optional[str] = None
    decorators: List[str] = Field(default_factory=list)
    parameters: List[ParameterMetadata] = Field(default_factory=list)
    return_annotation: Optional[str] = None
    parent_qualified_name: Optional[str] = None


class ImportEdge(BaseModel):
    """Discovered import relationship."""
    model_config = ConfigDict(frozen=True)

    id: str
    source_file: str
    source_module: str
    imported_name: str
    target_module: Optional[str] = None
    alias: Optional[str] = None
    kind: ImportKind
    resolution_status: ResolutionStatus
    line_number: int
    provenance: str = "ast_import"


class TestCase(BaseModel):
    """Discovered test unit and heuristic linkage."""
    __test__ = False
    model_config = ConfigDict(frozen=True)

    id: str
    file_path: str
    name: str
    qualified_name: str
    discovery_method: TestDiscoveryMethod
    line_number: int
    linked_symbols: List[str] = Field(default_factory=list)
    link_confidence: ConfidenceLevel = ConfidenceLevel.LOW


class ParseError(BaseModel):
    """Detailed error captured when a file fails parsing."""
    model_config = ConfigDict(frozen=True)

    line: Optional[int] = None
    column: Optional[int] = None
    error_type: str
    message: str


class IndexedFile(BaseModel):
    """Complete indexing metadata for a repository file."""
    model_config = ConfigDict(frozen=True)

    path: str
    size_bytes: int
    content_hash: str
    language: Language
    parse_status: ParseStatus
    symbols: List[Symbol] = Field(default_factory=list)
    imports: List[ImportEdge] = Field(default_factory=list)
    test_cases: List[TestCase] = Field(default_factory=list)
    parse_error: Optional[ParseError] = None


class SkippedFile(BaseModel):
    """Record of a file bypassed during traversal."""
    model_config = ConfigDict(frozen=True)

    path: str
    reason: SkipReason
    details: Optional[str] = None


class IndexSummary(BaseModel):
    """Aggregate statistics for an indexed snapshot."""
    model_config = ConfigDict(frozen=True)

    total_files_scanned: int
    indexed_python_files: int
    skipped_files: int
    parse_failures: int
    total_classes: int
    total_functions: int
    total_methods: int
    total_imports: int
    total_test_cases: int


class RepositorySnapshot(BaseModel):
    """Immutable, reproducible snapshot of a repository's intelligence index."""
    model_config = ConfigDict(frozen=True)

    repository_name: str
    repository_root_identifier: str
    ref_name: str
    commit_sha: str
    indexed_at: str
    indexer_version: str
    parser_version: str
    config_hash: str
    summary: IndexSummary
    files: Dict[str, IndexedFile]
    skipped_files: List[SkippedFile]
    parse_failures: List[str]
    unresolved_dependencies: List[str]
    warnings: List[str]

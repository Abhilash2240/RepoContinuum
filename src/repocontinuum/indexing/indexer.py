"""Orchestrator for repository intelligence indexing."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from repocontinuum.config import IndexerSettings
from repocontinuum.domain.models import (
    IndexedFile,
    IndexSummary,
    ParseStatus,
    RepositorySnapshot,
    SymbolKind,
)
from repocontinuum.indexing.ast_parser import PythonAstParser
from repocontinuum.indexing.file_walker import FileWalker
from repocontinuum.indexing.git_resolver import GitResolver
from repocontinuum.indexing.import_resolver import ImportResolver
from repocontinuum.indexing.test_discovery import PytestDiscoverer


class RepositoryIndexer:
    """Coordinates file traversal, AST parsing, import resolution, and test discovery."""

    def __init__(self, settings: Optional[IndexerSettings] = None):
        self.settings = settings or IndexerSettings()
        self.ast_parser = PythonAstParser()
        self.test_discoverer = PytestDiscoverer()

    def index_repository(self, repo_path: Path) -> RepositorySnapshot:
        """Execute full indexing workflow on a local Python repository."""
        resolved_repo_path = repo_path.resolve()
        if not resolved_repo_path.exists() or not resolved_repo_path.is_dir():
            raise ValueError(f"Target repository path is not a valid directory: {resolved_repo_path}")

        all_warnings: List[str] = []

        # 1. Resolve Git metadata
        git_resolver = GitResolver(resolved_repo_path)
        git_result = git_resolver.resolve()
        all_warnings.extend(git_result.warnings)

        # 2. Walk filesystem safely
        walker = FileWalker(
            repo_root=resolved_repo_path,
            ignored_directories=self.settings.ignored_directories,
            max_file_size_bytes=self.settings.max_file_size_bytes,
            include_untracked=self.settings.include_untracked,
        )
        walk_result = walker.walk()
        all_warnings.extend(walk_result.warnings)

        # 3. Parse AST for Python files
        raw_indexed_files: Dict[str, IndexedFile] = {}
        parse_failures: List[str] = []

        for py_path in walk_result.python_files:
            file_meta = self.ast_parser.parse_file(py_path, resolved_repo_path)
            raw_indexed_files[file_meta.path] = file_meta
            if file_meta.parse_status in {ParseStatus.SYNTAX_ERROR, ParseStatus.FAILED}:
                parse_failures.append(file_meta.path)
                if file_meta.parse_error:
                    all_warnings.append(
                        f"Parse warning in {file_meta.path} (line {file_meta.parse_error.line}): "
                        f"{file_meta.parse_error.error_type} - {file_meta.parse_error.message}"
                    )

        # 4. Map known internal modules and symbols for cross-referencing
        known_internal_modules: Set[str] = set()
        symbols_by_name: Dict[str, List[str]] = {}

        for rel_path, file_meta in raw_indexed_files.items():
            mod_name = self._derive_module_name(rel_path)
            known_internal_modules.add(mod_name)
            for sym in file_meta.symbols:
                if sym.kind != SymbolKind.MODULE:
                    symbols_by_name.setdefault(sym.name, []).append(sym.qualified_name)

        # 5. Resolve imports across files
        import_resolver = ImportResolver(known_internal_modules)
        resolved_files: Dict[str, IndexedFile] = {}
        unresolved_dependencies: Set[str] = set()

        for rel_path, file_meta in raw_indexed_files.items():
            mod_name = self._derive_module_name(rel_path)
            resolved_imports = import_resolver.resolve_imports(file_meta.imports, mod_name)

            for imp in resolved_imports:
                if imp.target_module and imp.kind.value == "unresolved":
                    unresolved_dependencies.add(imp.target_module)

            # Discover tests and establish candidate linkages
            test_cases = self.test_discoverer.discover_tests(file_meta, symbols_by_name)

            updated_file = file_meta.model_copy(
                update={
                    "imports": resolved_imports,
                    "test_cases": test_cases,
                }
            )
            resolved_files[rel_path] = updated_file

        # 6. Aggregate summary metrics
        total_classes = 0
        total_functions = 0
        total_methods = 0
        total_imports = 0
        total_test_cases = 0

        for file_meta in resolved_files.values():
            total_imports += len(file_meta.imports)
            total_test_cases += len(file_meta.test_cases)
            for sym in file_meta.symbols:
                if sym.kind == SymbolKind.CLASS:
                    total_classes += 1
                elif sym.kind in {SymbolKind.FUNCTION, SymbolKind.ASYNC_FUNCTION}:
                    total_functions += 1
                elif sym.kind in {SymbolKind.METHOD, SymbolKind.ASYNC_METHOD}:
                    total_methods += 1

        summary = IndexSummary(
            total_files_scanned=len(walk_result.python_files) + len(walk_result.skipped_files),
            indexed_python_files=len(resolved_files),
            skipped_files=len(walk_result.skipped_files),
            parse_failures=len(parse_failures),
            total_classes=total_classes,
            total_functions=total_functions,
            total_methods=total_methods,
            total_imports=total_imports,
            total_test_cases=total_test_cases,
        )

        now_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

        return RepositorySnapshot(
            repository_name=resolved_repo_path.name,
            repository_root_identifier=resolved_repo_path.name,
            ref_name=git_result.ref_name,
            commit_sha=git_result.commit_sha,
            indexed_at=now_utc,
            indexer_version=self.settings.indexer_version,
            parser_version=self.settings.parser_version,
            config_hash=self.settings.compute_config_hash(),
            summary=summary,
            files=resolved_files,
            skipped_files=walk_result.skipped_files,
            parse_failures=parse_failures,
            unresolved_dependencies=sorted(list(unresolved_dependencies)),
            warnings=all_warnings,
        )

    @staticmethod
    def _derive_module_name(file_path_posix: str) -> str:
        """Convert relative path to dotted Python module identifier."""
        path_without_ext = file_path_posix
        if path_without_ext.endswith((".py", ".pyi")):
            path_without_ext = path_without_ext.rsplit(".", 1)[0]
        parts = path_without_ext.split("/")
        if parts and parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts)

    @staticmethod
    def export_json(snapshot: RepositorySnapshot, output_path: Optional[Path] = None) -> str:
        """Export snapshot to machine-readable JSON string or file."""
        json_str = snapshot.model_dump_json(indent=2)
        if output_path:
            output_path.resolve().write_text(json_str, encoding="utf-8")
        return json_str

    @staticmethod
    def load_json(input_data: str | Path) -> RepositorySnapshot:
        """Load and validate a RepositorySnapshot from a JSON string or file."""
        if isinstance(input_data, Path):
            content = input_data.read_text(encoding="utf-8")
        else:
            content = input_data
        return RepositorySnapshot.model_validate_json(content)

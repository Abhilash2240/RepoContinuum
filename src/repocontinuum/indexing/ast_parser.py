"""Python AST metadata extraction engine."""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import List, Optional

from repocontinuum.domain.models import (
    ImportEdge,
    ImportKind,
    IndexedFile,
    Language,
    ParameterMetadata,
    ParseError,
    ParseStatus,
    ResolutionStatus,
    SourceLocation,
    Symbol,
    SymbolKind,
)


class AstSymbolVisitor(ast.NodeVisitor):
    """Walks Python AST to extract classes, functions, methods, decorators, and imports."""

    def __init__(self, file_path_posix: str):
        self.file_path_posix = file_path_posix
        self.symbols: List[Symbol] = []
        self.imports: List[ImportEdge] = []
        self.scope_stack: List[str] = []
        self.kind_stack: List[SymbolKind] = []

    def _current_qualified_name(self, name: str) -> str:
        """Construct full qualified name based on current scope."""
        if self.scope_stack:
            return ".".join(self.scope_stack) + "." + name
        return name

    def _current_parent_qualified_name(self) -> Optional[str]:
        """Get parent scope's qualified name if present."""
        if self.scope_stack:
            return ".".join(self.scope_stack)
        return None

    def _generate_symbol_id(self, qualified_name: str) -> str:
        """Create a stable deterministic 16-character identifier."""
        raw = f"{self.file_path_posix}:{qualified_name}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _generate_import_id(self, line: int, imported_name: str) -> str:
        """Create a stable identifier for an import relationship."""
        raw = f"{self.file_path_posix}:{line}:{imported_name}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def _extract_decorators(self, decorator_list: List[ast.expr]) -> List[str]:
        """Extract decorator expressions as source text."""
        decorators: List[str] = []
        for dec in decorator_list:
            try:
                decorators.append(ast.unparse(dec))
            except Exception:
                decorators.append("<unparseable_decorator>")
        return decorators

    def _extract_parameters(self, args_node: ast.arguments) -> List[ParameterMetadata]:
        """Extract function/method parameter signatures without evaluation."""
        params: List[ParameterMetadata] = []

        # Positional-only args
        for arg in args_node.posonlyargs:
            params.append(self._parse_single_arg(arg, "positional_only"))

        # Standard args (positional or keyword)
        # Note: defaults align to the right of standard args
        num_args = len(args_node.args)
        num_defaults = len(args_node.defaults)
        default_offset = num_args - num_defaults

        for idx, arg in enumerate(args_node.args):
            default_val = None
            if idx >= default_offset:
                def_node = args_node.defaults[idx - default_offset]
                try:
                    default_val = ast.unparse(def_node)
                except Exception:
                    default_val = "..."
            params.append(self._parse_single_arg(arg, "positional_or_keyword", default_val))

        # *args
        if args_node.vararg:
            params.append(self._parse_single_arg(args_node.vararg, "var_positional"))

        # Keyword-only args
        for idx, arg in enumerate(args_node.kwonlyargs):
            default_val = None
            if idx < len(args_node.kw_defaults) and args_node.kw_defaults[idx] is not None:
                try:
                    default_val = ast.unparse(args_node.kw_defaults[idx])
                except Exception:
                    default_val = "..."
            params.append(self._parse_single_arg(arg, "keyword_only", default_val))

        # **kwargs
        if args_node.kwarg:
            params.append(self._parse_single_arg(args_node.kwarg, "var_keyword"))

        return params

    def _parse_single_arg(
        self,
        arg_node: ast.arg,
        kind: str,
        default_value: Optional[str] = None,
    ) -> ParameterMetadata:
        """Convert an ast.arg node into a ParameterMetadata object."""
        annotation_text = None
        if arg_node.annotation is not None:
            try:
                annotation_text = ast.unparse(arg_node.annotation)
            except Exception:
                annotation_text = "<unparseable_annotation>"

        return ParameterMetadata(
            name=arg_node.arg,
            annotation=annotation_text,
            default_value=default_value,
            kind=kind,
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Extract class definition and traverse interior symbols."""
        qual_name = self._current_qualified_name(node.name)
        parent_qual = self._current_parent_qualified_name()
        loc = SourceLocation(
            start_line=node.lineno,
            start_col=node.col_offset,
            end_line=node.end_lineno or node.lineno,
            end_col=node.end_col_offset or node.col_offset,
        )

        symbol = Symbol(
            id=self._generate_symbol_id(qual_name),
            name=node.name,
            qualified_name=qual_name,
            kind=SymbolKind.CLASS,
            location=loc,
            docstring=ast.get_docstring(node),
            decorators=self._extract_decorators(node.decorator_list),
            parent_qualified_name=parent_qual,
        )
        self.symbols.append(symbol)

        # Enter class scope
        self.scope_stack.append(node.name)
        self.kind_stack.append(SymbolKind.CLASS)
        self.generic_visit(node)
        self.kind_stack.pop()
        self.scope_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Extract synchronous function or method."""
        self._handle_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Extract asynchronous function or method."""
        self._handle_function(node, is_async=True)

    def _handle_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        is_async: bool,
    ) -> None:
        qual_name = self._current_qualified_name(node.name)
        parent_qual = self._current_parent_qualified_name()

        is_inside_class = bool(self.kind_stack and self.kind_stack[-1] == SymbolKind.CLASS)
        if is_inside_class:
            kind = SymbolKind.ASYNC_METHOD if is_async else SymbolKind.METHOD
        else:
            kind = SymbolKind.ASYNC_FUNCTION if is_async else SymbolKind.FUNCTION

        return_annotation_text = None
        if node.returns is not None:
            try:
                return_annotation_text = ast.unparse(node.returns)
            except Exception:
                return_annotation_text = "<unparseable_return_annotation>"

        loc = SourceLocation(
            start_line=node.lineno,
            start_col=node.col_offset,
            end_line=node.end_lineno or node.lineno,
            end_col=node.end_col_offset or node.col_offset,
        )

        symbol = Symbol(
            id=self._generate_symbol_id(qual_name),
            name=node.name,
            qualified_name=qual_name,
            kind=kind,
            location=loc,
            docstring=ast.get_docstring(node),
            decorators=self._extract_decorators(node.decorator_list),
            parameters=self._extract_parameters(node.args),
            return_annotation=return_annotation_text,
            parent_qualified_name=parent_qual,
        )
        self.symbols.append(symbol)

        # Enter function scope
        self.scope_stack.append(node.name)
        self.kind_stack.append(kind)
        self.generic_visit(node)
        self.kind_stack.pop()
        self.scope_stack.pop()

    def visit_Import(self, node: ast.Import) -> None:
        """Capture direct import statement."""
        is_dynamic = bool(self.scope_stack)
        provenance = "dynamic_import" if is_dynamic else "ast_import"

        for alias in node.names:
            edge = ImportEdge(
                id=self._generate_import_id(node.lineno, alias.name),
                source_file=self.file_path_posix,
                source_module=self._derive_module_name(self.file_path_posix),
                imported_name=alias.name,
                target_module=alias.name,
                alias=alias.asname,
                kind=ImportKind.DYNAMIC if is_dynamic else ImportKind.UNRESOLVED,
                resolution_status=ResolutionStatus.DYNAMIC if is_dynamic else ResolutionStatus.UNRESOLVED,
                line_number=node.lineno,
                provenance=provenance,
            )
            self.imports.append(edge)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Capture from...import statement."""
        is_dynamic = bool(self.scope_stack)
        provenance = "dynamic_import_from" if is_dynamic else "ast_import_from"
        is_relative = (node.level or 0) > 0
        base_module = node.module or ""

        for alias in node.names:
            imported_full = f"{base_module}.{alias.name}" if base_module else alias.name
            kind = ImportKind.DYNAMIC if is_dynamic else (ImportKind.RELATIVE if is_relative else ImportKind.UNRESOLVED)
            edge = ImportEdge(
                id=self._generate_import_id(node.lineno, f"{base_module}:{alias.name}"),
                source_file=self.file_path_posix,
                source_module=self._derive_module_name(self.file_path_posix),
                imported_name=alias.name,
                target_module=base_module if base_module else None,
                alias=alias.asname,
                kind=kind,
                resolution_status=ResolutionStatus.DYNAMIC if is_dynamic else ResolutionStatus.UNRESOLVED,
                line_number=node.lineno,
                provenance=provenance,
            )
            self.imports.append(edge)

    @staticmethod
    def _derive_module_name(file_path_posix: str) -> str:
        """Derive standard Python dotted module path from relative POSIX path."""
        path_without_ext = file_path_posix
        if path_without_ext.endswith((".py", ".pyi")):
            path_without_ext = path_without_ext.rsplit(".", 1)[0]
        parts = path_without_ext.split("/")
        if parts and parts[-1] == "__init__":
            parts.pop()
        return ".".join(parts)


class PythonAstParser:
    """Parses Python source files using standard library AST with error containment."""

    def parse_file(self, file_path: Path, repo_root: Path) -> IndexedFile:
        """Parse a single Python file and return an IndexedFile record."""
        try:
            rel_posix = file_path.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            rel_posix = file_path.name

        try:
            raw_bytes = file_path.read_bytes()
        except OSError as e:
            return IndexedFile(
                path=rel_posix,
                size_bytes=0,
                content_hash="",
                language=Language.PYTHON,
                parse_status=ParseStatus.FAILED,
                parse_error=ParseError(
                    error_type=type(e).__name__,
                    message=f"Filesystem read error: {e}",
                ),
            )

        content_hash = hashlib.sha256(raw_bytes).hexdigest()
        size_bytes = len(raw_bytes)

        # Decode content with UTF-8 fallback
        try:
            source_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                source_text = raw_bytes.decode("utf-8-sig")
            except UnicodeDecodeError as ue:
                return IndexedFile(
                    path=rel_posix,
                    size_bytes=size_bytes,
                    content_hash=content_hash,
                    language=Language.PYTHON,
                    parse_status=ParseStatus.FAILED,
                    parse_error=ParseError(
                        line=None,
                        column=None,
                        error_type="UnicodeDecodeError",
                        message=f"Failed to decode source text as UTF-8: {ue}",
                    ),
                )

        # Parse AST
        try:
            tree = ast.parse(source_text, filename=rel_posix)
        except SyntaxError as se:
            return IndexedFile(
                path=rel_posix,
                size_bytes=size_bytes,
                content_hash=content_hash,
                language=Language.PYTHON,
                parse_status=ParseStatus.SYNTAX_ERROR,
                parse_error=ParseError(
                    line=se.lineno,
                    column=se.offset,
                    error_type="SyntaxError",
                    message=str(se.msg),
                ),
            )
        except Exception as ex:
            return IndexedFile(
                path=rel_posix,
                size_bytes=size_bytes,
                content_hash=content_hash,
                language=Language.PYTHON,
                parse_status=ParseStatus.FAILED,
                parse_error=ParseError(
                    error_type=type(ex).__name__,
                    message=f"Unexpected AST parse exception: {ex}",
                ),
            )

        # Visit and extract symbols
        visitor = AstSymbolVisitor(file_path_posix=rel_posix)
        visitor.visit(tree)

        # Add module-level docstring if present
        module_doc = ast.get_docstring(tree)
        if module_doc:
            module_symbol = Symbol(
                id=hashlib.sha256(f"{rel_posix}:__doc__".encode("utf-8")).hexdigest()[:16],
                name=rel_posix,
                qualified_name=visitor._derive_module_name(rel_posix),
                kind=SymbolKind.MODULE,
                location=SourceLocation(start_line=1, start_col=0, end_line=1, end_col=0),
                docstring=module_doc,
            )
            visitor.symbols.insert(0, module_symbol)

        return IndexedFile(
            path=rel_posix,
            size_bytes=size_bytes,
            content_hash=content_hash,
            language=Language.PYTHON,
            parse_status=ParseStatus.PARSED,
            symbols=visitor.symbols,
            imports=visitor.imports,
            test_cases=[],
            parse_error=None,
        )

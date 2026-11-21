"""Pytest test file, test class, and test function discovery engine."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List, Set

from repocontinuum.domain.models import (
    ConfidenceLevel,
    IndexedFile,
    Symbol,
    SymbolKind,
    TestCase,
    TestDiscoveryMethod,
)


class PytestDiscoverer:
    """Discovers pytest test cases and links them heuristically to source code symbols."""

    @staticmethod
    def is_test_file(rel_posix_path: str) -> bool:
        """Determine if a file path is a pytest test file."""
        path = Path(rel_posix_path)
        stem = path.stem.lower()

        # Naming convention: test_*.py or *_test.py
        if stem.startswith("test_") or stem.endswith("_test"):
            return True

        # Path convention: inside tests/ or test/ directory
        parts = [p.lower() for p in path.parts]
        if "tests" in parts or "test" in parts:
            if path.suffix.lower() in {".py", ".pyi"}:
                return True

        return False

    def discover_tests(
        self,
        indexed_file: IndexedFile,
        all_symbols_by_name: Dict[str, List[str]],  # symbol_name -> list of qualified_names
    ) -> List[TestCase]:
        """Extract test cases from an indexed file and establish candidate source linkages."""
        if not self.is_test_file(indexed_file.path):
            return []

        test_cases: List[TestCase] = []

        # Find imported symbol names in this test file
        imported_names = {edge.imported_name for edge in indexed_file.imports}

        for sym in indexed_file.symbols:
            # 1. Test functions (top-level)
            if sym.kind in {SymbolKind.FUNCTION, SymbolKind.ASYNC_FUNCTION}:
                if sym.name.startswith("test_") or sym.name.startswith("test"):
                    test_cases.append(
                        self._create_test_case(
                            indexed_file.path,
                            sym,
                            TestDiscoveryMethod.PYTEST_FUNCTION,
                            imported_names,
                            all_symbols_by_name,
                        )
                    )

            # 2. Test methods inside test classes
            elif sym.kind in {SymbolKind.METHOD, SymbolKind.ASYNC_METHOD}:
                if sym.name.startswith("test_"):
                    # Check if parent is a Test* class
                    parent_name = sym.parent_qualified_name.split(".")[-1] if sym.parent_qualified_name else ""
                    if parent_name.startswith("Test"):
                        test_cases.append(
                            self._create_test_case(
                                indexed_file.path,
                                sym,
                                TestDiscoveryMethod.PYTEST_METHOD,
                                imported_names,
                                all_symbols_by_name,
                            )
                        )

            # 3. Test classes
            elif sym.kind == SymbolKind.CLASS:
                if sym.name.startswith("Test"):
                    test_cases.append(
                        self._create_test_case(
                            indexed_file.path,
                            sym,
                            TestDiscoveryMethod.PYTEST_CLASS,
                            imported_names,
                            all_symbols_by_name,
                        )
                    )

        return test_cases

    def _create_test_case(
        self,
        file_path: str,
        sym: Symbol,
        method: TestDiscoveryMethod,
        imported_names: Set[str],
        all_symbols_by_name: Dict[str, List[str]],
    ) -> TestCase:
        """Create a TestCase record with heuristic linkage."""
        linked_symbols: List[str] = []
        confidence = ConfidenceLevel.LOW

        # Heuristic 1: Strip prefixes and suffixes from test name
        raw_name = sym.name
        if raw_name.startswith("test_"):
            candidate_base = raw_name[5:]
        elif raw_name.startswith("Test"):
            candidate_base = raw_name[4:]
        else:
            candidate_base = raw_name

        # Candidates to check: exact base, and base with common suffixes removed
        candidate_forms = [candidate_base]
        for suffix in ("_method", "_function", "_func", "_test", "_suite"):
            if candidate_base.endswith(suffix):
                candidate_forms.append(candidate_base[: -len(suffix)])

        # Also check word tokens
        candidate_forms.extend(candidate_base.split("_"))

        for cand in candidate_forms:
            if cand and cand in all_symbols_by_name:
                for target_qual in all_symbols_by_name[cand]:
                    if target_qual not in linked_symbols:
                        linked_symbols.append(target_qual)
                        if cand in imported_names:
                            confidence = ConfidenceLevel.HIGH
                        elif confidence != ConfidenceLevel.HIGH:
                            confidence = ConfidenceLevel.MEDIUM

        # Heuristic 2: Any imported internal symbols
        for imp in imported_names:
            if imp in all_symbols_by_name:
                for target_qual in all_symbols_by_name[imp]:
                    if target_qual not in linked_symbols:
                        linked_symbols.append(target_qual)

        test_id = hashlib.sha256(f"{file_path}:{sym.qualified_name}".encode("utf-8")).hexdigest()[:16]

        return TestCase(
            id=test_id,
            file_path=file_path,
            name=sym.name,
            qualified_name=sym.qualified_name,
            discovery_method=method,
            line_number=sym.location.start_line,
            linked_symbols=linked_symbols,
            link_confidence=confidence,
        )

"""Import resolution engine classifying standard-library, relative, internal, and external imports."""

from __future__ import annotations

import sys
from typing import Dict, List, Optional, Set

from repocontinuum.domain.models import ImportEdge, ImportKind, ResolutionStatus


class ImportResolver:
    """Resolves import edges against Python standard library and discovered internal modules."""

    def __init__(self, known_internal_modules: Set[str]):
        self.known_internal_modules = known_internal_modules
        # Python 3.10+ has sys.stdlib_module_names
        self.stdlib_modules = getattr(sys, "stdlib_module_names", set())

    def resolve_imports(
        self,
        imports: List[ImportEdge],
        source_module: str,
    ) -> List[ImportEdge]:
        """Classify and resolve a list of import edges for a given module."""
        resolved: List[ImportEdge] = []

        for edge in imports:
            if edge.kind == ImportKind.DYNAMIC:
                # Dynamic imports remain classified as dynamic with high uncertainty
                resolved.append(edge)
                continue

            target = edge.target_module or edge.imported_name
            top_level = target.split(".")[0] if target else ""

            # 1. Check Standard Library
            if top_level in self.stdlib_modules:
                resolved.append(
                    edge.model_copy(
                        update={
                            "kind": ImportKind.STANDARD_LIBRARY,
                            "resolution_status": ResolutionStatus.RESOLVED,
                        }
                    )
                )
                continue

            # 2. Check Relative Import
            if edge.kind == ImportKind.RELATIVE:
                resolved_rel = self._resolve_relative_module(source_module, target)
                if resolved_rel and self._is_internal_module(resolved_rel):
                    resolved.append(
                        edge.model_copy(
                            update={
                                "target_module": resolved_rel,
                                "kind": ImportKind.INTERNAL,
                                "resolution_status": ResolutionStatus.RESOLVED,
                            }
                        )
                    )
                else:
                    resolved.append(
                        edge.model_copy(
                            update={
                                "target_module": resolved_rel or target,
                                "kind": ImportKind.RELATIVE,
                                "resolution_status": (
                                    ResolutionStatus.RESOLVED if resolved_rel else ResolutionStatus.UNRESOLVED
                                ),
                            }
                        )
                    )
                continue

            # 3. Check Internal Module
            if self._is_internal_module(target):
                resolved.append(
                    edge.model_copy(
                        update={
                            "kind": ImportKind.INTERNAL,
                            "resolution_status": ResolutionStatus.RESOLVED,
                        }
                    )
                )
                continue

            # 4. Third-Party External
            resolved.append(
                edge.model_copy(
                    update={
                        "kind": ImportKind.THIRD_PARTY,
                        "resolution_status": ResolutionStatus.EXTERNAL,
                    }
                )
            )

        return resolved

    def _is_internal_module(self, target_module: str) -> bool:
        """Check if target module or its prefix belongs to internal modules."""
        if not target_module:
            return False
        if target_module in self.known_internal_modules:
            return True
        # Check if parent package is internal
        parts = target_module.split(".")
        for i in range(len(parts), 0, -1):
            prefix = ".".join(parts[:i])
            if prefix in self.known_internal_modules:
                return True
        return False

    def _resolve_relative_module(self, source_module: str, target_module: Optional[str]) -> Optional[str]:
        """Resolve dotted relative import against the package of the source module."""
        source_parts = source_module.split(".") if source_module else []
        # Package is the parent of the source module
        package_parts = source_parts[:-1] if source_parts else []

        if not target_module:
            return ".".join(package_parts) if package_parts else None

        # Clean leading dots
        leading_dots = 0
        for char in target_module:
            if char == ".":
                leading_dots += 1
            else:
                break

        sub_module = target_module[leading_dots:]

        # One dot means current package, two dots means parent, etc.
        traverse_up = leading_dots - 1
        if traverse_up > len(package_parts):
            return None  # Escapes top-level package

        base_parts = package_parts[: len(package_parts) - traverse_up] if traverse_up > 0 else package_parts
        if sub_module:
            base_parts.append(sub_module)

        return ".".join(base_parts)

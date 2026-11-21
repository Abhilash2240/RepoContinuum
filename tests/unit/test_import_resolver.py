"""Unit tests for import resolution engine."""

import pytest
from repocontinuum.domain.models import ImportEdge, ImportKind, ResolutionStatus
from repocontinuum.indexing.import_resolver import ImportResolver


def test_standard_library_resolution() -> None:
    """Verify that standard library modules are classified as standard_library."""
    resolver = ImportResolver(known_internal_modules={"my_app"})
    edges = [
        ImportEdge(
            id="1",
            source_file="my_app/main.py",
            source_module="my_app.main",
            imported_name="os",
            target_module="os",
            kind=ImportKind.UNRESOLVED,
            resolution_status=ResolutionStatus.UNRESOLVED,
            line_number=1,
        ),
        ImportEdge(
            id="2",
            source_file="my_app/main.py",
            source_module="my_app.main",
            imported_name="json",
            target_module="json",
            kind=ImportKind.UNRESOLVED,
            resolution_status=ResolutionStatus.UNRESOLVED,
            line_number=2,
        ),
    ]

    resolved = resolver.resolve_imports(edges, "my_app.main")
    assert all(e.kind == ImportKind.STANDARD_LIBRARY for e in resolved)
    assert all(e.resolution_status == ResolutionStatus.RESOLVED for e in resolved)


def test_internal_and_third_party_resolution() -> None:
    """Verify distinction between internal repo packages and external third party."""
    resolver = ImportResolver(known_internal_modules={"my_pkg.service", "my_pkg.models"})
    edges = [
        ImportEdge(
            id="1",
            source_file="my_pkg/service.py",
            source_module="my_pkg.service",
            imported_name="models",
            target_module="my_pkg.models",
            kind=ImportKind.UNRESOLVED,
            resolution_status=ResolutionStatus.UNRESOLVED,
            line_number=1,
        ),
        ImportEdge(
            id="2",
            source_file="my_pkg/service.py",
            source_module="my_pkg.service",
            imported_name="FastAPI",
            target_module="fastapi",
            kind=ImportKind.UNRESOLVED,
            resolution_status=ResolutionStatus.UNRESOLVED,
            line_number=2,
        ),
    ]

    resolved = resolver.resolve_imports(edges, "my_pkg.service")
    assert resolved[0].kind == ImportKind.INTERNAL
    assert resolved[0].resolution_status == ResolutionStatus.RESOLVED

    assert resolved[1].kind == ImportKind.THIRD_PARTY
    assert resolved[1].resolution_status == ResolutionStatus.EXTERNAL


def test_relative_import_resolution() -> None:
    """Verify resolution of relative dots (. and ..) into absolute internal module names."""
    resolver = ImportResolver(known_internal_modules={"pkg.sub.helper", "pkg.config"})
    edges = [
        ImportEdge(
            id="1",
            source_file="pkg/sub/main.py",
            source_module="pkg.sub.main",
            imported_name="run",
            target_module=".helper",
            kind=ImportKind.RELATIVE,
            resolution_status=ResolutionStatus.UNRESOLVED,
            line_number=1,
        ),
        ImportEdge(
            id="2",
            source_file="pkg/sub/main.py",
            source_module="pkg.sub.main",
            imported_name="settings",
            target_module="..config",
            kind=ImportKind.RELATIVE,
            resolution_status=ResolutionStatus.UNRESOLVED,
            line_number=2,
        ),
    ]

    resolved = resolver.resolve_imports(edges, "pkg.sub.main")
    assert resolved[0].target_module == "pkg.sub.helper"
    assert resolved[0].kind == ImportKind.INTERNAL
    assert resolved[0].resolution_status == ResolutionStatus.RESOLVED

    assert resolved[1].target_module == "pkg.config"
    assert resolved[1].kind == ImportKind.INTERNAL
    assert resolved[1].resolution_status == ResolutionStatus.RESOLVED

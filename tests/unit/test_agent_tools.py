"""Unit tests for ToolDispatcher: allowlist enforcement, path security, size limits, and budgets."""

from pathlib import Path
import pytest

from repocontinuum.agent.schemas.tool_intent import ToolIntent
from repocontinuum.agent.tools.dispatcher import ToolDispatcher
from repocontinuum.domain.models import (
    ImportEdge,
    ImportKind,
    IndexedFile,
    IndexSummary,
    Language,
    ParameterMetadata,
    ParseStatus,
    RepositorySnapshot,
    ResolutionStatus,
    SourceLocation,
    Symbol,
    SymbolKind,
    TestCase,
    TestDiscoveryMethod,
)
from repocontinuum.persistence.database import DatabaseManager
from repocontinuum.persistence.repository import TaskChainRepository
from repocontinuum.planning.service import TaskChainService


@pytest.fixture
def sample_tool_env(tmp_path: Path):
    """Set up a test repository and indexed snapshot for tool dispatcher tests."""
    repo_dir = tmp_path / "tool_repo"
    repo_dir.mkdir()
    src_dir = repo_dir / "src"
    src_dir.mkdir()

    hello_file = src_dir / "hello.py"
    hello_file.write_text(
        "import sys\n\ndef greet(name: str) -> str:\n    \"\"\"Say hello.\"\"\"\n    return f'Hello {name}'\n",
        encoding="utf-8",
    )

    test_file = repo_dir / "test_hello.py"
    test_file.write_text(
        "from src.hello import greet\n\ndef test_greet():\n    assert greet('World') == 'Hello World'\n",
        encoding="utf-8",
    )

    # Protected file
    env_file = repo_dir / ".env"
    env_file.write_text("SECRET_KEY=supersecret123\n", encoding="utf-8")

    db = DatabaseManager(database_url=f"sqlite:///{tmp_path / 'tool_test.db'}")
    db.create_tables()
    repo = TaskChainRepository(db)
    service = TaskChainService(repo)
    chain = service.create_chain(title="Tool Chain", repository_id="tool-repo")
    task = service.add_task(chain_id=chain.id, title="Tool Task")

    snapshot = RepositorySnapshot(
        repository_name="tool-repo",
        repository_root_identifier="tool-root",
        ref_name="refs/heads/main",
        commit_sha="b" * 40,
        indexed_at="2026-11-21T00:00:00Z",
        indexer_version="1.0.0",
        parser_version="1.0.0",
        config_hash="cfg-tool",
        summary=IndexSummary(
            total_files_scanned=2,
            indexed_python_files=2,
            skipped_files=0,
            parse_failures=0,
            total_classes=0,
            total_functions=1,
            total_methods=0,
            total_imports=1,
            total_test_cases=1,
        ),
        files={
            "src/hello.py": IndexedFile(
                path="src/hello.py",
                size_bytes=hello_file.stat().st_size,
                content_hash="h1",
                language=Language.PYTHON,
                parse_status=ParseStatus.PARSED,
                symbols=[
                    Symbol(
                        id="s-1",
                        name="greet",
                        qualified_name="greet",
                        kind=SymbolKind.FUNCTION,
                        location=SourceLocation(start_line=3, start_col=0, end_line=5, end_col=27),
                        docstring="Say hello.",
                        parameters=[ParameterMetadata(name="name")],
                    )
                ],
                imports=[
                    ImportEdge(
                        id="imp-1",
                        source_file="src/hello.py",
                        source_module="hello",
                        imported_name="sys",
                        target_module="sys",
                        alias=None,
                        kind=ImportKind.STANDARD_LIBRARY,
                        resolution_status=ResolutionStatus.RESOLVED,
                        line_number=1,
                    )
                ],
            ),
            "test_hello.py": IndexedFile(
                path="test_hello.py",
                size_bytes=test_file.stat().st_size,
                content_hash="h2",
                language=Language.PYTHON,
                parse_status=ParseStatus.PARSED,
                test_cases=[
                    TestCase(
                        id="tc-1",
                        name="test_greet",
                        qualified_name="test_greet",
                        file_path="test_hello.py",
                        discovery_method=TestDiscoveryMethod.PYTEST_FUNCTION,
                        line_number=3,
                    )
                ],
            ),
        },
        skipped_files=[],
        parse_failures=[],
        unresolved_dependencies=[],
        warnings=[],
    )

    dispatcher = ToolDispatcher(
        repo_path=repo_dir,
        snapshot=snapshot,
        service=service,
        max_tool_calls=5,
    )

    return {
        "dispatcher": dispatcher,
        "task_id": task.id,
        "chain_id": chain.id,
    }


def test_approved_read_tools(sample_tool_env):
    """Verify approved read tools execute successfully."""
    dispatcher = sample_tool_env["dispatcher"]

    # 1. Summary
    res_sum = dispatcher.dispatch(ToolIntent(tool_name="get_repository_summary", arguments={}, purpose="p", expected_result="e"))
    assert res_sum.success is True
    assert res_sum.data["total_files"] == 2

    # 2. Search symbols
    res_sym = dispatcher.dispatch(ToolIntent(tool_name="search_symbols", arguments={"query": "greet"}, purpose="p", expected_result="e"))
    assert res_sym.success is True
    assert len(res_sym.data) == 1
    assert res_sym.data[0]["name"] == "greet"

    # 3. Get symbol source
    res_src = dispatcher.dispatch(
        ToolIntent(tool_name="get_symbol_source", arguments={"file_path": "src/hello.py", "symbol_name": "greet"}, purpose="p", expected_result="e")
    )
    assert res_src.success is True
    assert "def greet" in res_src.data["code"]

    # 4. Get file content
    res_cnt = dispatcher.dispatch(
        ToolIntent(tool_name="get_file_content", arguments={"file_path": "src/hello.py", "start_line": 1, "end_line": 3}, purpose="p", expected_result="e")
    )
    assert res_cnt.success is True
    assert "import sys" in res_cnt.data["content"]


def test_unapproved_tool_rejected(sample_tool_env):
    """Verify tools outside the allowlist are rejected."""
    dispatcher = sample_tool_env["dispatcher"]
    intent = ToolIntent(tool_name="execute_bash_command", arguments={"cmd": "ls"}, purpose="p", expected_result="e")
    res = dispatcher.dispatch(intent)
    assert res.success is False
    assert "not in the approved tool registry" in res.error


def test_tool_path_traversal_rejected(sample_tool_env):
    """Verify path traversal is caught and rejected."""
    dispatcher = sample_tool_env["dispatcher"]
    intent = ToolIntent(tool_name="get_file_content", arguments={"file_path": "../../../etc/passwd"}, purpose="p", expected_result="e")
    res = dispatcher.dispatch(intent)
    assert res.success is False
    assert "traversal" in res.error.lower()


def test_tool_protected_path_rejected(sample_tool_env):
    """Verify access to protected files (.env) is denied."""
    dispatcher = sample_tool_env["dispatcher"]
    intent = ToolIntent(tool_name="get_file_content", arguments={"file_path": ".env"}, purpose="p", expected_result="e")
    res = dispatcher.dispatch(intent)
    assert res.success is False
    assert "protected path" in res.error.lower()


def test_tool_call_budget_enforcement(sample_tool_env):
    """Verify dispatcher halts when max tool call limit is reached."""
    dispatcher = sample_tool_env["dispatcher"]
    # max_tool_calls is 5
    for i in range(5):
        res = dispatcher.dispatch(ToolIntent(tool_name="get_repository_summary", arguments={}, purpose="p", expected_result="e"))
        assert res.success is True

    # 6th call should fail due to budget
    res_budget = dispatcher.dispatch(ToolIntent(tool_name="get_repository_summary", arguments={}, purpose="p", expected_result="e"))
    assert res_budget.success is False
    assert "Tool call budget exceeded" in res_budget.error

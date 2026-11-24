"""Unit tests for sandbox runners, isolation options, and fail-closed security."""

import pytest
from pathlib import Path
from repocontinuum.domain.verification import CheckStatus
from repocontinuum.execution.allowlist import CommandSecurityError
from repocontinuum.execution.sandbox import DockerSandboxRunner, FakeSandboxRunner


def test_docker_sandbox_fails_closed_when_daemon_stopped(tmp_path: Path) -> None:
    """CRITICAL SECURITY REQUIREMENT: If Docker daemon is stopped, fail closed with NOT_RUN."""
    runner = DockerSandboxRunner()

    if not runner.is_available():
        res = runner.run(["python", "-m", "py_compile", "app.py"], tmp_path)
        assert res.status == CheckStatus.NOT_RUN
        assert res.executed_in_sandbox is False
        assert "Docker daemon is not running" in res.stderr
        assert res.exit_code is None


def test_docker_sandbox_successful_execution_when_available(tmp_path: Path) -> None:
    """Verify DockerSandboxRunner executes container command with strict security flags when Docker is available."""
    from unittest.mock import MagicMock, patch

    runner = DockerSandboxRunner(image_tag="repocontinuum-sandbox:test")

    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = "All tests passed"
    mock_proc.stderr = ""

    with patch.object(runner, "is_available", return_value=True), patch("subprocess.run", return_value=mock_proc) as mock_run:
        res = runner.run(["pytest", "tests/"], tmp_path)

        assert res.status == CheckStatus.PASSED
        assert res.exit_code == 0
        assert res.executed_in_sandbox is True
        assert "All tests passed" in res.stdout

        # Verify strict container security flags in constructed command
        called_cmd = mock_run.call_args[0][0]
        assert called_cmd[0] == "docker"
        assert called_cmd[1] == "run"
        assert "--network" in called_cmd and "none" in called_cmd
        assert "--read-only" in called_cmd
        assert "--cap-drop=ALL" in called_cmd
        assert "--security-opt=no-new-privileges:true" in called_cmd
        assert "repocontinuum-sandbox:test" in called_cmd


def test_fake_sandbox_runner_enforces_allowlist(tmp_path: Path) -> None:
    """Verify that fake sandbox runner still strictly validates command allowlists."""
    fake = FakeSandboxRunner()

    # Allowlisted command succeeds
    res = fake.run(["python", "-m", "pytest", "tests/"], tmp_path)
    assert res.status == CheckStatus.PASSED
    assert res.executed_in_sandbox is True

    # Non-allowlisted command rejected even by fake runner
    with pytest.raises(CommandSecurityError):
        fake.run(["bash", "-c", "whoami"], tmp_path)


def test_fake_sandbox_runner_simulates_failure(tmp_path: Path) -> None:
    """Verify simulated failure response in fake sandbox."""
    fake = FakeSandboxRunner(default_status=CheckStatus.FAILED, default_exit_code=1, default_stderr="AssertionError in test")
    res = fake.run(["pytest", "tests/"], tmp_path)

    assert res.status == CheckStatus.FAILED
    assert res.exit_code == 1
    assert "AssertionError" in res.stderr


def test_fake_sandbox_runner_simulates_unavailable(tmp_path: Path) -> None:
    """Verify fake runner returns NOT_RUN when set to unavailable."""
    fake = FakeSandboxRunner(available=False)
    assert fake.is_available() is False

    res = fake.run(["pytest"], tmp_path)
    assert res.status == CheckStatus.NOT_RUN
    assert res.executed_in_sandbox is False

"""Sandbox execution adapters enforcing isolation, resource limits, and fail-closed security."""

from __future__ import annotations

import abc
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from repocontinuum.domain.verification import CheckStatus
from repocontinuum.execution.allowlist import CommandAllowlistValidator, SecretRedactor


@dataclass(frozen=True)
class SandboxResult:
    """Outcome of executing an allowlisted command in a sandbox."""
    status: CheckStatus
    exit_code: Optional[int]
    duration_ms: int
    stdout: str
    stderr: str
    executed_in_sandbox: bool
    message: str = ""


class BaseSandboxRunner(abc.ABC):
    """Abstract interface for verification sandbox runners."""

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Check if the isolation environment is currently healthy and accessible."""
        pass

    @abc.abstractmethod
    def run(
        self,
        command_args: List[str],
        workspace_path: Path,
        timeout_sec: int = 60,
    ) -> SandboxResult:
        """Execute a command within the isolated sandbox."""
        pass


class DockerSandboxRunner(BaseSandboxRunner):
    """Disposable Linux container runner with strict resource and security constraints."""

    DEFAULT_IMAGE = os.environ.get("REPOCONTINUUM_SANDBOX_IMAGE", "python:3.13-slim")

    def __init__(
        self,
        image_tag: Optional[str] = None,
        cpus: float = 1.0,
        memory_limit: str = "512m",
        pids_limit: int = 64,
    ):
        self.image_tag = image_tag or self.DEFAULT_IMAGE
        self.cpus = cpus
        self.memory_limit = memory_limit
        self.pids_limit = pids_limit

    def is_available(self) -> bool:
        """Probe Docker daemon to ensure container engine is running."""
        try:
            proc = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            return proc.returncode == 0
        except (subprocess.SubprocessError, OSError):
            return False

    def run(
        self,
        command_args: List[str],
        workspace_path: Path,
        timeout_sec: int = 60,
    ) -> SandboxResult:
        """Execute an allowlisted command in a locked-down Docker container, failing closed if unavailable."""
        # 1. Allowlist enforcement
        validated_args = CommandAllowlistValidator.validate_command(command_args)

        # 2. Check daemon availability — FAIL CLOSED
        if not self.is_available():
            return SandboxResult(
                status=CheckStatus.NOT_RUN,
                exit_code=None,
                duration_ms=0,
                stdout="",
                stderr="Docker daemon is not running. Verification failed closed to prevent unisolated host execution.",
                executed_in_sandbox=False,
                message="Docker sandbox unavailable; execution refused for safety.",
            )

        resolved_ws = workspace_path.resolve()
        # Convert path for Docker volume mount across Windows / WSL
        # On Windows, drive letter format C:\... is mounted as /c/... or standard Windows docker volume
        docker_mount = str(resolved_ws)

        docker_cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--read-only",
            "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges:true",
            f"--cpus={self.cpus}",
            f"--memory={self.memory_limit}",
            f"--pids-limit={self.pids_limit}",
            "-v", f"{docker_mount}:/workspace:rw",
            "-w", "/workspace",
            self.image_tag,
            *validated_args,
        ]

        start_time = time.monotonic()
        try:
            proc = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
            duration_ms = int((time.monotonic() - start_time) * 1000)

            redacted_stdout = SecretRedactor.redact(proc.stdout)
            redacted_stderr = SecretRedactor.redact(proc.stderr)

            status = CheckStatus.PASSED if proc.returncode == 0 else CheckStatus.FAILED

            return SandboxResult(
                status=status,
                exit_code=proc.returncode,
                duration_ms=duration_ms,
                stdout=redacted_stdout,
                stderr=redacted_stderr,
                executed_in_sandbox=True,
                message="Execution completed in Docker container.",
            )

        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return SandboxResult(
                status=CheckStatus.TIMED_OUT,
                exit_code=None,
                duration_ms=duration_ms,
                stdout="",
                stderr=f"Command timed out after {timeout_sec} seconds.",
                executed_in_sandbox=True,
                message=f"Process exceeded timeout limit ({timeout_sec}s).",
            )
        except Exception as ex:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return SandboxResult(
                status=CheckStatus.INCONCLUSIVE,
                exit_code=None,
                duration_ms=duration_ms,
                stdout="",
                stderr=f"Execution failed due to unexpected error: {ex}",
                executed_in_sandbox=False,
                message="Unexpected sandbox execution error.",
            )


class FakeSandboxRunner(BaseSandboxRunner):
    """Deterministic test double for unit testing verification pipelines without Docker."""

    def __init__(
        self,
        default_status: CheckStatus = CheckStatus.PASSED,
        default_exit_code: int = 0,
        default_stdout: str = "Fake execution output",
        default_stderr: str = "",
        available: bool = True,
        command_responses: Optional[Dict[str, SandboxResult]] = None,
        canned_results: Optional[Dict[str, SandboxResult]] = None,
    ):
        self._available = available
        self.default_status = default_status
        self.default_exit_code = default_exit_code
        self.default_stdout = default_stdout
        self.default_stderr = default_stderr
        self.command_responses = command_responses or canned_results or {}
        self.executed_commands: List[List[str]] = []

    def is_available(self) -> bool:
        return self._available

    def run(
        self,
        command_args: List[str],
        workspace_path: Path,
        timeout_sec: int = 60,
    ) -> SandboxResult:
        # Validate allowlist even in fake sandbox to guarantee tests verify security gates
        validated_args = CommandAllowlistValidator.validate_command(command_args)
        self.executed_commands.append(validated_args)

        if not self._available:
            return SandboxResult(
                status=CheckStatus.NOT_RUN,
                exit_code=None,
                duration_ms=0,
                stdout="",
                stderr="Sandbox unavailable; failed closed.",
                executed_in_sandbox=False,
                message="Sandbox unavailable.",
            )

        cmd_key = " ".join(validated_args)
        if cmd_key in self.command_responses:
            return self.command_responses[cmd_key]

        return SandboxResult(
            status=self.default_status,
            exit_code=self.default_exit_code,
            duration_ms=15,
            stdout=SecretRedactor.redact(self.default_stdout),
            stderr=SecretRedactor.redact(self.default_stderr),
            executed_in_sandbox=True,
            message="Executed in fake sandbox.",
        )

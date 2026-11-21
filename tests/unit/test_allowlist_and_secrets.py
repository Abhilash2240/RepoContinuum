"""Unit tests for command allowlist enforcement and secret redaction."""

import pytest
from repocontinuum.execution.allowlist import (
    CommandAllowlistValidator,
    CommandSecurityError,
    SecretRedactor,
)


def test_allowlisted_commands_pass() -> None:
    """Verify supported profiles pass allowlist checks."""
    assert CommandAllowlistValidator.validate_command(["python", "-m", "py_compile", "src/app.py"])
    assert CommandAllowlistValidator.validate_command(["python", "-m", "pytest", "-v", "tests/test_auth.py"])
    assert CommandAllowlistValidator.validate_command(["pytest", "-k", "test_login"])
    assert CommandAllowlistValidator.validate_command(["ruff", "check", "src/"])


def test_non_allowlisted_commands_rejected() -> None:
    """Verify arbitrary or hazardous commands are rejected."""
    with pytest.raises(CommandSecurityError, match="outside the verification allowlist"):
        CommandAllowlistValidator.validate_command(["bash", "-c", "echo pwned"])

    with pytest.raises(CommandSecurityError, match="outside the verification allowlist"):
        CommandAllowlistValidator.validate_command(["curl", "https://attacker.com"])

    with pytest.raises(CommandSecurityError, match="outside the verification allowlist"):
        CommandAllowlistValidator.validate_command(["powershell", "Get-Process"])

    with pytest.raises(CommandSecurityError, match="outside the verification allowlist"):
        CommandAllowlistValidator.validate_command(["pip", "install", "malicious-pkg"])


def test_shell_metacharacters_rejected() -> None:
    """Verify shell operators (;, &&, |, &, >, <) inside arguments are strictly rejected."""
    with pytest.raises(CommandSecurityError, match="Forbidden shell metacharacter"):
        CommandAllowlistValidator.validate_command(["pytest", "tests/; rm -rf /"])

    with pytest.raises(CommandSecurityError, match="Forbidden shell metacharacter"):
        CommandAllowlistValidator.validate_command(["pytest", "tests/ && cat /etc/passwd"])

    with pytest.raises(CommandSecurityError, match="Forbidden shell metacharacter"):
        CommandAllowlistValidator.validate_command(["pytest", "tests/ | sh"])

    with pytest.raises(CommandSecurityError, match="Forbidden shell metacharacter"):
        CommandAllowlistValidator.validate_command(["pytest", "> output.txt"])


def test_path_traversal_in_command_arguments_rejected() -> None:
    """Verify .. traversal inside command paths is rejected."""
    with pytest.raises(CommandSecurityError, match="Path traversal in command argument"):
        CommandAllowlistValidator.validate_command(["pytest", "../../../outside_tests/"])


def test_secret_redactor_jwt_token() -> None:
    """Verify JWT tokens are redacted from log strings."""
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkFsaWNlIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    raw_log = f"Failed to authenticate with token {jwt} on endpoint /login"
    redacted = SecretRedactor.redact(raw_log)

    assert jwt not in redacted
    assert "[REDACTED_SECRET]" in redacted


def test_secret_redactor_private_key() -> None:
    """Verify private keys are redacted from logs."""
    priv_key = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA04...sample...\n-----END RSA PRIVATE KEY-----"
    raw_log = f"Loaded server key:\n{priv_key}\nStarting listener"
    redacted = SecretRedactor.redact(raw_log)

    assert "MIIEow" not in redacted
    assert "[REDACTED_SECRET]" in redacted


def test_secret_redactor_api_key_and_password() -> None:
    """Verify api_key=... and password=... fields are redacted."""
    raw_log = "Error connecting with api_key='sk_live_123456789abcdef0123' and password='SuperSecretPassword123'"
    redacted = SecretRedactor.redact(raw_log)

    assert "sk_live_123456789abcdef0123" not in redacted
    assert "SuperSecretPassword123" not in redacted
    assert "api_key=[REDACTED_SECRET]" in redacted or "[REDACTED_SECRET]" in redacted

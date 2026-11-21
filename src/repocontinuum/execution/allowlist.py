"""Command allowlist validation, argument inspection, and secret redaction."""

from __future__ import annotations

import re
from typing import List, Tuple


class CommandSecurityError(Exception):
    """Raised when an un-allowlisted or hazardous command is requested."""


class SecretRedactor:
    """Detects and redacts sensitive tokens, keys, and credentials from logs."""

    PATTERNS: List[re.Pattern] = [
        # Private keys
        re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----.*?-----END [A-Z ]+ PRIVATE KEY-----", re.DOTALL),
        # JWT tokens
        re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+"),
        # Generic API keys / tokens (key=..., token=..., secret=...)
        re.compile(r"(?i)(api[_-]?key|access[_-]?token|secret|password|bearer)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.\/]{12,})['\"]?"),
        # AWS access keys
        re.compile(r"(?i)(AKIA|ASIA)[0-9A-Z]{16}"),
    ]

    @classmethod
    def redact(cls, text: str) -> str:
        """Replace likely secrets and sensitive tokens with [REDACTED_SECRET]."""
        if not text:
            return ""

        result = text
        for pattern in cls.PATTERNS:
            def repl(m: re.Match) -> str:
                # If matched group has label and value, preserve label
                if m.lastindex and m.lastindex >= 2:
                    return f"{m.group(1)}=[REDACTED_SECRET]"
                return "[REDACTED_SECRET]"
            result = pattern.sub(repl, result)

        return result


class CommandAllowlistValidator:
    """Enforces strict allowlist rules on commands executed in verification sandboxes."""

    FORBIDDEN_CHARACTERS: List[str] = [";", "&&", "||", "|", "&", ">", "<", "`", "$"]

    ALLOWED_BINARY_PREFIXES: List[Tuple[str, ...]] = [
        ("python", "-m", "py_compile"),
        ("python", "-m", "pytest"),
        ("pytest",),
        ("ruff", "check"),
    ]

    @classmethod
    def validate_command(cls, command_args: List[str]) -> List[str]:
        """Validate argument list against command allowlist rules."""
        if not command_args:
            raise CommandSecurityError("Command argument list cannot be empty.")

        # Check for prohibited shell operators inside individual arguments
        for arg in command_args:
            for forbidden in cls.FORBIDDEN_CHARACTERS:
                if forbidden in arg:
                    raise CommandSecurityError(
                        f"Forbidden shell metacharacter '{forbidden}' in argument '{arg}'."
                    )

        # Match prefix against allowed profiles
        matched = False
        cmd_tuple = tuple(command_args)

        for prefix in cls.ALLOWED_BINARY_PREFIXES:
            prefix_len = len(prefix)
            if len(command_args) >= prefix_len and tuple(command_args[:prefix_len]) == prefix:
                matched = True
                cls._validate_options(prefix[0], command_args[prefix_len:])
                break

        if not matched:
            cmd_summary = " ".join(command_args[:3])
            raise CommandSecurityError(
                f"Command '{cmd_summary}...' is outside the verification allowlist."
            )

        return command_args

    @classmethod
    def _validate_options(cls, base_cmd: str, options: List[str]) -> None:
        """Validate trailing flags and paths."""
        for opt in options:
            # Traversal check in command argument
            if ".." in opt.replace("\\", "/").split("/"):
                raise CommandSecurityError(f"Path traversal in command argument is prohibited: '{opt}'")

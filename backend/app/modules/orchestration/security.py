from __future__ import annotations

import re
from dataclasses import dataclass
import shlex
from collections.abc import Mapping
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class CommandValidationError(Exception):
    """Raised when command input is unsafe for shell interpolation."""


class CredentialResolutionError(Exception):
    """Raised when credential-backed command material cannot be resolved safely."""


class SSHExecutionError(Exception):
    """Raised when SSH execution fails inside the runtime boundary."""


class WorkflowExecutionError(Exception):
    """Raised when workflow orchestration fails."""


class DeploymentExecutionError(Exception):
    """Raised when deployment orchestration fails."""


class SecretSanitizer:
    """Central redaction utility for runtime output, logs, and metadata."""

    REDACTED = "********"
    SECRET_PATTERNS = (
        re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
        re.compile(r"(?i)(api[_-]?key|token|secret|password|passphrase)\s*[:=]\s*([^\s,;]+)"),
        re.compile(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
    )

    def __init__(self, explicit_secrets: list[str] | None = None) -> None:
        self._explicit_secrets = [secret for secret in explicit_secrets or [] if secret]

    def add_secret(self, secret: str | None) -> None:
        if secret and secret not in self._explicit_secrets:
            self._explicit_secrets.append(secret)

    def redact_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        redacted = value
        for secret in sorted(self._explicit_secrets, key=len, reverse=True):
            if secret:
                redacted = redacted.replace(secret, self.REDACTED)
        for pattern in self.SECRET_PATTERNS:
            redacted = pattern.sub(lambda match: match.group(0).split(match.group(2))[0] + self.REDACTED if len(match.groups()) >= 2 else self.REDACTED, redacted)
        return redacted

    def redact_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.redact_text(value)
        if isinstance(value, list):
            return [self.redact_value(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.redact_value(item) for item in value)
        if isinstance(value, Mapping):
            return {
                key: self.REDACTED if self._sensitive_key(str(key)) else self.redact_value(item)
                for key, item in value.items()
            }
        return value

    @staticmethod
    def _sensitive_key(key: str) -> bool:
        lowered = key.lower()
        return any(token in lowered for token in ("password", "secret", "token", "api_key", "apikey", "private_key", "passphrase"))


def redact_sensitive_text(value: str | None, *, secrets: list[str] | None = None) -> str | None:
    return SecretSanitizer(secrets).redact_text(value)


def redact_sensitive_value(value: Any, *, secrets: list[str] | None = None) -> Any:
    return SecretSanitizer(secrets).redact_value(value)


class SafeCommandBuilder:
    """Validates command templates while preserving legitimate shell scripts."""

    DANGEROUS_INTERPOLATION_PATTERNS = (
        re.compile(r";"),
        re.compile(r"&&"),
        re.compile(r"\|\|"),
        re.compile(r"\$\("),
        re.compile(r"`"),
        re.compile(r"[\r\n]"),
    )

    def __init__(self, variable_service) -> None:
        self.variable_service = variable_service

    def validate_command(self, command: str, *, source: str, allow_shell_operators: bool = True) -> None:
        if not command.strip():
            raise CommandValidationError("Command cannot be empty")
        if allow_shell_operators:
            if self._has_dangerous_tokens(command):
                logger.info("command_contains_shell_operators", source=source)
            return
        self._validate_value(command, source=source)

    def resolve_template(
        self,
        template: str,
        *,
        definitions: list[dict[str, Any]],
        variables: dict[str, str],
        source: str,
    ) -> str:
        escaped_variables = {
            name: self.escape_interpolated_value(name, value, source=source)
            for name, value in variables.items()
        }
        resolved = self.variable_service.resolve_text(
            template,
            definitions=definitions,
            variables=escaped_variables,
        )
        self.validate_command(resolved, source=source, allow_shell_operators=True)
        return resolved

    def escape_interpolated_value(self, name: str, value: str, *, source: str) -> str:
        self._validate_value(value, source=f"{source}:{name}")
        return shlex.quote(str(value))

    def _validate_value(self, value: str, *, source: str) -> None:
        if self._has_dangerous_tokens(value):
            logger.warning("unsafe_command_interpolation_rejected", source=source)
            raise CommandValidationError(
                f"Unsafe shell control token detected in interpolated value for {source}"
            )

    @classmethod
    def _has_dangerous_tokens(cls, value: str) -> bool:
        return any(pattern.search(value) for pattern in cls.DANGEROUS_INTERPOLATION_PATTERNS)


@dataclass(frozen=True)
class CommandPolicyResult:
    policy: str
    reason: str | None = None


class CommandPolicyEngine:
    """Small policy layer for shell execution governance."""

    HARD_DENIED_PATTERNS = (
        re.compile(r"\brm\s+-rf\s+/(?:\s|$)"),
        re.compile(r"\bdd\s+.*\bof=/dev/"),
    )
    INTENTIONAL_DESTRUCTIVE_PATTERNS = (
        re.compile(r"\bmkfs(?:\.[a-z0-9]+)?\b"),
    )
    APPROVAL_PATTERNS = (
        re.compile(r"\bshutdown\b"),
        re.compile(r"\breboot\b"),
        re.compile(r"\bdocker\s+system\s+prune\b"),
        re.compile(r"\bterraform\s+destroy\b"),
        re.compile(r"\brm\s+-rf\b"),
    )

    def evaluate(self, command: str, *, allow_destructive: bool = False) -> CommandPolicyResult:
        lowered = command.lower()
        for pattern in self.HARD_DENIED_PATTERNS:
            if pattern.search(lowered):
                return CommandPolicyResult("denied", pattern.pattern)
        for pattern in self.INTENTIONAL_DESTRUCTIVE_PATTERNS:
            if pattern.search(lowered):
                if allow_destructive:
                    return CommandPolicyResult("approval_required", pattern.pattern)
                return CommandPolicyResult("denied", pattern.pattern)
        for pattern in self.APPROVAL_PATTERNS:
            if pattern.search(lowered):
                return CommandPolicyResult("approval_required", pattern.pattern)
        return CommandPolicyResult("allowed")

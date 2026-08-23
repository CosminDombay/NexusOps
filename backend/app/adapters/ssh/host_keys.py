"""Shared SSH host-key pinning for every outbound connection.

Both the automation execution adapter and the interactive remote-access adapter
route their host-key decisions through :class:`HostKeyPolicy` so that a pinned
fingerprint is enforced identically no matter which subsystem opens the
connection.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime

import paramiko
import structlog

logger = structlog.get_logger(__name__)


class HostKeyVerificationError(Exception):
    """Raised when a host key is untrusted or does not match the pinned fingerprint."""


def host_key_fingerprint_sha256(key: paramiko.PKey) -> str:
    """Return the OpenSSH-style ``SHA256:<base64>`` fingerprint for a host key."""
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def legacy_hex_fingerprint(key: paramiko.PKey) -> str:
    """Return the historical hex-encoded fingerprint format.

    Fingerprints recorded before the switch to OpenSSH-style base64 encoding are
    stored in this shape. Accepting it keeps already-pinned hosts working instead
    of failing every connection until an operator re-approves them.
    """
    return "SHA256:" + hashlib.sha256(key.asbytes()).hexdigest()


class HostKeyPolicy(paramiko.MissingHostKeyPolicy):
    """Pin a host key, or record it on first use when no pin exists yet.

    A policy instance is single-use: it carries the fingerprint accepted during
    the connection it was passed to, so the caller can persist a first-use pin.
    """

    def __init__(self, expected_fingerprint: str | None, *, trust_on_first_use: bool) -> None:
        self.expected_fingerprint = (expected_fingerprint or "").strip() or None
        self.trust_on_first_use = trust_on_first_use
        self.accepted_fingerprint: str | None = None
        self.newly_accepted_fingerprint: str | None = None

    @classmethod
    def for_server(cls, server, *, trust_on_first_use: bool | None = None) -> HostKeyPolicy:
        """Build a policy from an inventory server's stored pin."""
        from backend.app.core.config import settings

        return cls(
            getattr(server, "trusted_ssh_host_key_sha256", None),
            trust_on_first_use=(
                settings.ssh_trust_on_first_use if trust_on_first_use is None else trust_on_first_use
            ),
        )

    def missing_host_key(self, client: paramiko.SSHClient, hostname: str, key: paramiko.PKey) -> None:
        fingerprint = host_key_fingerprint_sha256(key)

        if self.expected_fingerprint:
            if self.expected_fingerprint not in {fingerprint, legacy_hex_fingerprint(key)}:
                logger.warning(
                    "ssh.host_key_mismatch",
                    host=hostname,
                    expected=self.expected_fingerprint,
                    presented=fingerprint,
                )
                raise HostKeyVerificationError(
                    f"SSH host key fingerprint mismatch for {hostname}: "
                    f"expected {self.expected_fingerprint}, got {fingerprint}"
                )
            self.accepted_fingerprint = self.expected_fingerprint
            client.get_host_keys().add(hostname, key.get_name(), key)
            return

        if not self.trust_on_first_use:
            logger.warning("ssh.host_key_untrusted", host=hostname, presented=fingerprint)
            raise HostKeyVerificationError(
                f"SSH host key for {hostname} is not trusted and trust-on-first-use is disabled"
            )

        logger.warning("ssh.host_key_trusted_on_first_use", host=hostname, fingerprint=fingerprint)
        self.accepted_fingerprint = fingerprint
        self.newly_accepted_fingerprint = fingerprint
        client.get_host_keys().add(hostname, key.get_name(), key)

    def persist_to(self, server) -> bool:
        """Store a first-use fingerprint on the server record. Returns True if changed.

        The caller's unit of work is responsible for committing.
        """
        if not self.newly_accepted_fingerprint:
            return False
        if getattr(server, "trusted_ssh_host_key_sha256", None):
            return False
        server.trusted_ssh_host_key_sha256 = self.newly_accepted_fingerprint
        server.trusted_ssh_host_key_accepted_at = datetime.now(UTC)
        return True

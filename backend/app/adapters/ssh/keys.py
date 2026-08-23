"""Shared private-key loading for the SSH execution and remote-access adapters."""

from __future__ import annotations

import io

import paramiko

# Resolved at import time so a paramiko upgrade that drops a key type degrades to
# "unsupported key format" instead of raising AttributeError at connection time.
_KEY_CLASS_NAMES = ("Ed25519Key", "RSAKey", "ECDSAKey", "DSSKey")
KEY_CLASSES: tuple[type[paramiko.PKey], ...] = tuple(
    key_class
    for key_class in (getattr(paramiko, name, None) for name in _KEY_CLASS_NAMES)
    if key_class is not None
)


class PrivateKeyLoadError(Exception):
    """Raised when an inline private key cannot be parsed."""


def load_private_key(private_key: str | None, passphrase: str | None) -> paramiko.PKey | None:
    """Parse an inline PEM/OpenSSH private key, trying each supported key type."""
    if not private_key:
        return None

    key_stream = io.StringIO(private_key)
    passphrase_required = False
    for key_class in KEY_CLASSES:
        key_stream.seek(0)
        try:
            return key_class.from_private_key(key_stream, password=passphrase)
        except paramiko.PasswordRequiredException:
            passphrase_required = True
        except paramiko.SSHException:
            continue

    if passphrase_required and not passphrase:
        raise PrivateKeyLoadError("SSH private key is passphrase-protected but no passphrase was supplied")
    if passphrase:
        raise PrivateKeyLoadError("SSH private key could not be decrypted; check the passphrase and key format")
    raise PrivateKeyLoadError("Unsupported SSH private key format")

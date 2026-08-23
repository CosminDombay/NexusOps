"""Regression tests for inline SSH private-key loading.

These exercise the real paramiko key classes rather than mocks, because the
adapters previously referenced a key class that a paramiko major release had
removed. That failure was invisible to every mocked SSH test.
"""

import paramiko
import pytest

from backend.app.adapters.ssh.keys import KEY_CLASSES, PrivateKeyLoadError, load_private_key
from backend.app.adapters.ssh.paramiko import ParamikoSshAdapter, SshConnectionError
from backend.app.modules.remote_access.service import (
    ParamikoRemoteAccessAdapter,
    RemoteSshError,
    SshConnectionDetails,
)


def _generate(key_class, passphrase=None, **kwargs) -> str:
    import io

    key = key_class.generate(**kwargs)
    buffer = io.StringIO()
    key.write_private_key(buffer, password=passphrase)
    return buffer.getvalue()


@pytest.fixture(scope="module")
def ed25519_key() -> str:
    # Ed25519Key has no generate(); round-trip a freshly created OpenSSH key instead.
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519

    private_key = ed25519.Ed25519PrivateKey.generate()
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


@pytest.fixture(scope="module")
def rsa_key() -> str:
    return _generate(paramiko.RSAKey, bits=2048)


def test_key_classes_are_resolvable() -> None:
    assert KEY_CLASSES, "no paramiko key classes resolved; check the installed paramiko version"
    names = {key_class.__name__ for key_class in KEY_CLASSES}
    assert {"Ed25519Key", "RSAKey", "ECDSAKey"} <= names


def test_loads_rsa_key(rsa_key: str) -> None:
    assert isinstance(load_private_key(rsa_key, None), paramiko.RSAKey)


def test_loads_ed25519_key(ed25519_key: str) -> None:
    assert isinstance(load_private_key(ed25519_key, None), paramiko.Ed25519Key)


def test_loads_passphrase_protected_key() -> None:
    encrypted = _generate(paramiko.RSAKey, passphrase="secret123", bits=2048)
    assert isinstance(load_private_key(encrypted, "secret123"), paramiko.RSAKey)


def test_missing_passphrase_is_reported() -> None:
    encrypted = _generate(paramiko.RSAKey, passphrase="secret123", bits=2048)
    with pytest.raises(PrivateKeyLoadError, match="passphrase"):
        load_private_key(encrypted, None)


def test_wrong_passphrase_is_reported() -> None:
    encrypted = _generate(paramiko.RSAKey, passphrase="secret123", bits=2048)
    with pytest.raises(PrivateKeyLoadError, match="passphrase"):
        load_private_key(encrypted, "wrong")


def test_absent_key_returns_none() -> None:
    assert load_private_key(None, None) is None
    assert load_private_key("", None) is None


def test_garbage_key_is_rejected() -> None:
    with pytest.raises(PrivateKeyLoadError, match="Unsupported"):
        load_private_key("-----BEGIN OPENSSH PRIVATE KEY-----\nnope\n-----END OPENSSH PRIVATE KEY-----", None)


def test_execution_adapter_surfaces_key_errors(rsa_key: str) -> None:
    assert isinstance(ParamikoSshAdapter._pkey(rsa_key, None), paramiko.RSAKey)
    with pytest.raises(SshConnectionError):
        ParamikoSshAdapter._pkey("not-a-key", None)


def test_remote_access_adapter_surfaces_key_errors(rsa_key: str) -> None:
    details = SshConnectionDetails(host="h", port=22, username="u", private_key=rsa_key)
    assert isinstance(ParamikoRemoteAccessAdapter._pkey(details), paramiko.RSAKey)

    broken = SshConnectionDetails(host="h", port=22, username="u", private_key="not-a-key")
    with pytest.raises(RemoteSshError):
        ParamikoRemoteAccessAdapter._pkey(broken)

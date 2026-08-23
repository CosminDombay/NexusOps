"""Host-key pinning tests covering both SSH paths.

The automation adapter previously accepted any host key on every connection
while only the interactive remote-access path pinned fingerprints. Both now
share one policy, so these tests assert the shared behaviour directly.
"""

import paramiko
import pytest

from backend.app.adapters.ssh.host_keys import (
    HostKeyPolicy,
    HostKeyVerificationError,
    host_key_fingerprint_sha256,
    legacy_hex_fingerprint,
)


class _FakeHostKeys:
    def __init__(self) -> None:
        self.added: list[tuple[str, str]] = []

    def add(self, hostname: str, keytype: str, key) -> None:
        self.added.append((hostname, keytype))


class _FakeClient:
    def __init__(self) -> None:
        self._host_keys = _FakeHostKeys()

    def get_host_keys(self) -> _FakeHostKeys:
        return self._host_keys


@pytest.fixture(scope="module")
def host_key() -> paramiko.PKey:
    return paramiko.RSAKey.generate(bits=2048)


@pytest.fixture(scope="module")
def other_key() -> paramiko.PKey:
    return paramiko.RSAKey.generate(bits=2048)


def test_fingerprint_is_openssh_base64_format(host_key: paramiko.PKey) -> None:
    fingerprint = host_key_fingerprint_sha256(host_key)
    assert fingerprint.startswith("SHA256:")
    body = fingerprint.removeprefix("SHA256:")
    assert not body.endswith("=")
    # 32 raw bytes base64-encoded without padding.
    assert len(body) == 43


def test_first_use_records_fingerprint(host_key: paramiko.PKey) -> None:
    policy = HostKeyPolicy(None, trust_on_first_use=True)
    client = _FakeClient()

    policy.missing_host_key(client, "host-a", host_key)

    assert policy.accepted_fingerprint == host_key_fingerprint_sha256(host_key)
    assert policy.newly_accepted_fingerprint == policy.accepted_fingerprint
    assert client.get_host_keys().added == [("host-a", host_key.get_name())]


def test_first_use_refused_when_tofu_disabled(host_key: paramiko.PKey) -> None:
    policy = HostKeyPolicy(None, trust_on_first_use=False)

    with pytest.raises(HostKeyVerificationError, match="not trusted"):
        policy.missing_host_key(_FakeClient(), "host-a", host_key)

    assert policy.accepted_fingerprint is None


def test_matching_pin_is_accepted(host_key: paramiko.PKey) -> None:
    expected = host_key_fingerprint_sha256(host_key)
    policy = HostKeyPolicy(expected, trust_on_first_use=False)

    policy.missing_host_key(_FakeClient(), "host-a", host_key)

    assert policy.accepted_fingerprint == expected
    # An already-pinned host must not be re-persisted.
    assert policy.newly_accepted_fingerprint is None


def test_mismatched_pin_is_rejected(host_key: paramiko.PKey, other_key: paramiko.PKey) -> None:
    policy = HostKeyPolicy(host_key_fingerprint_sha256(host_key), trust_on_first_use=True)

    with pytest.raises(HostKeyVerificationError, match="mismatch"):
        policy.missing_host_key(_FakeClient(), "host-a", other_key)

    assert policy.accepted_fingerprint is None


def test_mismatch_wins_over_trust_on_first_use(host_key: paramiko.PKey, other_key: paramiko.PKey) -> None:
    """A stored pin must never be silently replaced, even with TOFU enabled."""
    policy = HostKeyPolicy(host_key_fingerprint_sha256(host_key), trust_on_first_use=True)

    with pytest.raises(HostKeyVerificationError):
        policy.missing_host_key(_FakeClient(), "host-a", other_key)


def test_legacy_hex_pin_still_matches(host_key: paramiko.PKey) -> None:
    """Fingerprints stored in the pre-base64 format keep working."""
    policy = HostKeyPolicy(legacy_hex_fingerprint(host_key), trust_on_first_use=False)

    policy.missing_host_key(_FakeClient(), "host-a", host_key)

    assert policy.accepted_fingerprint == legacy_hex_fingerprint(host_key)


class _Server:
    def __init__(self, fingerprint: str | None = None) -> None:
        self.trusted_ssh_host_key_sha256 = fingerprint
        self.trusted_ssh_host_key_accepted_at = None


def test_for_server_uses_stored_pin(host_key: paramiko.PKey) -> None:
    expected = host_key_fingerprint_sha256(host_key)
    policy = HostKeyPolicy.for_server(_Server(expected))
    assert policy.expected_fingerprint == expected


def test_persist_to_records_first_use(host_key: paramiko.PKey) -> None:
    server = _Server()
    policy = HostKeyPolicy.for_server(server, trust_on_first_use=True)
    policy.missing_host_key(_FakeClient(), "host-a", host_key)

    assert policy.persist_to(server) is True
    assert server.trusted_ssh_host_key_sha256 == host_key_fingerprint_sha256(host_key)
    assert server.trusted_ssh_host_key_accepted_at is not None


def test_persist_to_never_overwrites_existing_pin(host_key: paramiko.PKey) -> None:
    server = _Server("SHA256:previously-approved")
    policy = HostKeyPolicy.for_server(server)
    policy.newly_accepted_fingerprint = host_key_fingerprint_sha256(host_key)

    assert policy.persist_to(server) is False
    assert server.trusted_ssh_host_key_sha256 == "SHA256:previously-approved"


def test_blank_stored_pin_is_treated_as_absent() -> None:
    policy = HostKeyPolicy.for_server(_Server("   "))
    assert policy.expected_fingerprint is None

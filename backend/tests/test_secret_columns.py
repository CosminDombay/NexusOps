"""Encryption-at-rest for inline secrets stored on domain records.

Server.ssh_password used to be written to the database in plaintext even though
the Credential Manager encrypted everything it held. These tests assert the
ciphertext never resembles the plaintext on disk, and that rows written before
the change stay readable.
"""

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.app.db.base import Base
from backend.app.db.types import EncryptedString
from backend.app.modules.credentials.encryption_service import EncryptionService
from backend.app.modules.inventory.models import Server

PLAINTEXT = "sup3r-secret-ssh-passw0rd"


@pytest.fixture()
def master_key(monkeypatch) -> str:
    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setattr("backend.app.core.config.settings.nexusops_master_key", key)
    return key


@pytest.fixture()
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'secrets.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def _server(**overrides) -> Server:
    fields = {
        "hostname": "host-1",
        "ip_address": "10.0.0.5",
        "operating_system": "ubuntu-24.04",
        "environment": "development",
        "provider": "manual",
        "ssh_username": "root",
        "ssh_password": PLAINTEXT,
    }
    fields.update(overrides)
    return Server(**fields)


def _write_legacy_plaintext_row(engine, hostname: str = "legacy") -> None:
    """Create a row whose ssh_password is stored as plaintext, as before this change."""
    with Session(engine) as session:
        session.add(_server(hostname=hostname, ssh_password=None))
        session.commit()
    with engine.connect() as connection:
        connection.execute(
            text("UPDATE servers SET ssh_password = :password WHERE hostname = :hostname"),
            {"password": PLAINTEXT, "hostname": hostname},
        )
        connection.commit()


def test_ssh_password_column_is_encrypted() -> None:
    assert isinstance(Server.__table__.c.ssh_password.type, EncryptedString)


def test_password_is_ciphertext_on_disk(engine, master_key) -> None:
    with Session(engine) as session:
        session.add(_server())
        session.commit()

    with engine.connect() as connection:
        stored = connection.execute(text("SELECT ssh_password FROM servers")).scalar_one()

    assert stored != PLAINTEXT
    assert PLAINTEXT not in stored
    assert stored.startswith("gAAAAA")
    # Recoverable with the configured key, and only with that key.
    assert EncryptionService(master_key).decrypt_value(stored) == PLAINTEXT


def test_password_round_trips_through_the_orm(engine, master_key) -> None:
    with Session(engine) as session:
        session.add(_server())
        session.commit()

    with Session(engine) as session:
        assert session.query(Server).one().ssh_password == PLAINTEXT


def test_legacy_plaintext_rows_stay_readable(engine, master_key) -> None:
    """Rows written before the column was encrypted must not break reads."""
    _write_legacy_plaintext_row(engine)

    with Session(engine) as session:
        legacy = session.query(Server).filter_by(hostname="legacy").one()
        assert legacy.ssh_password == PLAINTEXT


def test_legacy_row_is_encrypted_on_next_write(engine, master_key) -> None:
    _write_legacy_plaintext_row(engine)

    with Session(engine) as session:
        legacy = session.query(Server).filter_by(hostname="legacy").one()
        legacy.ssh_password = "rotated-password"
        session.commit()

    with engine.connect() as connection:
        stored = connection.execute(
            text("SELECT ssh_password FROM servers WHERE hostname = 'legacy'")
        ).scalar_one()
    assert stored.startswith("gAAAAA")
    assert "rotated-password" not in stored


def test_null_and_empty_values_pass_through(engine, master_key) -> None:
    with Session(engine) as session:
        session.add(_server(hostname="no-password", ssh_password=None))
        session.commit()

    with Session(engine) as session:
        assert session.query(Server).filter_by(hostname="no-password").one().ssh_password is None


def test_without_master_key_value_still_round_trips(engine, monkeypatch) -> None:
    """Unconfigured local setups keep working rather than failing every write."""
    monkeypatch.setattr("backend.app.core.config.settings.nexusops_master_key", None)

    with Session(engine) as session:
        session.add(_server())
        session.commit()

    with Session(engine) as session:
        assert session.query(Server).one().ssh_password == PLAINTEXT

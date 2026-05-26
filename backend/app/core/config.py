import json
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "staging", "production"]


class ProductionConfigurationError(RuntimeError):
    """Raised when production startup would use unsafe configuration."""


class Settings(BaseSettings):
    environment: Environment = "development"
    debug: bool = False
    log_level: str = "INFO"
    secret_key: str = Field(default="change-me", min_length=8)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=15, ge=5, le=60)
    refresh_token_expire_days: int = Field(default=30, ge=1, le=90)
    session_inactivity_timeout_minutes: int = Field(default=480, ge=15, le=43200)
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    database_url: str = "postgresql+asyncpg://nexusops:nexusops@localhost:5432/nexusops"

    proxmox_api_url: str | None = None
    proxmox_verify_ssl: bool = False
    proxmox_token_id: str | None = None
    proxmox_token_secret: str | None = None
    proxmox_timeout_seconds: int = Field(default=15, ge=1, le=120)

    ssh_default_port: int = 22
    ssh_connect_timeout_seconds: int = 15
    ssh_command_timeout_seconds: int = Field(default=60, ge=1, le=3600)
    ssh_private_key_path: str | None = None
    prometheus_api_url: str | None = None
    grafana_base_url: str | None = None
    loki_base_url: str | None = None
    monitoring_timeout_seconds: int = Field(default=10, ge=1, le=60)
    monitoring_validation_interval_seconds: int = Field(default=300, ge=60, le=86400)
    runtime_refresh_enabled: bool = True
    runtime_refresh_interval_seconds: int = Field(default=60, ge=30, le=3600)
    runtime_refresh_min_interval_seconds: int = Field(default=30, ge=10, le=3600)
    runtime_refresh_concurrency: int = Field(default=4, ge=1, le=20)
    runtime_refresh_timeout_seconds: int = Field(default=45, ge=10, le=300)
    nexusops_master_key: str | None = None
    nexusops_admin_user: str | None = None
    nexusops_admin_email: str | None = None
    nexusops_admin_password: str | None = None
    allow_insecure_dev_secrets: bool = False
    allow_insecure_dev_tls: bool = False
    enable_openapi: bool = True
    rate_limit_enabled: bool = True
    api_rate_limit_per_minute: int = Field(default=600, ge=10, le=10000)
    login_rate_limit_per_minute: int = Field(default=10, ge=1, le=300)
    websocket_rate_limit_per_minute: int = Field(default=30, ge=1, le=600)
    remote_access_token_expire_seconds: int = Field(default=45, ge=15, le=120)
    ssh_trust_on_first_use: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ValueError("CORS_ORIGINS must be a JSON array or comma-separated list") from exc
                if not isinstance(parsed, list) or not all(isinstance(origin, str) for origin in parsed):
                    raise ValueError("CORS_ORIGINS JSON value must be an array of strings")
                return [origin.strip() for origin in parsed if origin.strip()]
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    def startup_warnings(self) -> list[str]:
        warnings = []
        if self.secret_key == "change-me":
            warnings.append("SECRET_KEY is using the development default.")
        if not self.nexusops_master_key:
            warnings.append("NEXUSOPS_MASTER_KEY is not configured; credential encryption is unavailable.")
        if not self.proxmox_verify_ssl:
            warnings.append("Proxmox TLS certificate verification is disabled.")
        return warnings

    def validate_startup_configuration(self) -> None:
        if not self.is_production:
            return
        errors = []
        if self.secret_key == "change-me":
            errors.append("SECRET_KEY must be set to a non-default value.")
        if self.debug:
            errors.append("DEBUG must be disabled in production.")
        if not self.nexusops_master_key:
            errors.append("NEXUSOPS_MASTER_KEY is required in production.")
        if not self.proxmox_verify_ssl:
            errors.append("PROXMOX_VERIFY_SSL must be true in production.")
        if self.nexusops_admin_password and self.nexusops_admin_password.lower() in {
            "admin",
            "password",
            "password123",
            "password123!",
            "changeme",
            "change-me",
            "nexusops",
        }:
            errors.append("Bootstrap admin password looks like a default credential.")
        if errors:
            raise ProductionConfigurationError("Unsafe production configuration: " + " ".join(errors))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

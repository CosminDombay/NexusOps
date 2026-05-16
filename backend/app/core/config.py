from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    log_level: str = "INFO"
    secret_key: str = Field(default="change-me", min_length=8)
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
    monitoring_timeout_seconds: int = Field(default=10, ge=1, le=60)
    nexusops_master_key: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

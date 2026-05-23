from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MonitoringProviderStatusRead(BaseModel):
    provider_type: str
    configured: bool
    reachable: bool
    integration_id: UUID | None = None
    url: str | None = None
    error: str | None = None
    role: str = "telemetry_provider"


class MonitoringMetricRead(BaseModel):
    name: str
    value: float | None = None
    unit: str


class ServerMetricsRead(BaseModel):
    server_id: UUID
    hostname: str
    ip_address: str
    monitoring_targets: list[str] = Field(default_factory=list)
    monitoring_interface: str | None = None
    monitoring_strategy: str = "host"
    online: bool
    cpu_usage_percent: float | None = None
    memory_usage_percent: float | None = None
    disk_usage_percent: float | None = None
    uptime_seconds: float | None = None
    grafana_url: str | None = None
    prometheus_url: str | None = None
    loki_url: str | None = None
    advanced_metrics_url: str | None = None
    container_metrics_url: str | None = None
    advanced_logs_url: str | None = None
    open_grafana_url: str | None = None
    metrics_error: str | None = None
    logs_error: str | None = None
    monitoring_state: str = "unknown"
    monitoring_status: str = "Unknown"
    node_exporter_status: str = "unknown"
    promtail_status: str = "unknown"
    cadvisor_status: str = "unknown"
    prometheus_target_health: str = "unknown"
    metrics_available: bool = False
    logs_available: bool = False
    node_exporter_detected: bool = False
    node_exporter_reachable: bool = False
    cadvisor_detected: bool = False
    cadvisor_running: bool = False
    docker_runtime_available: bool = False
    promtail_detected: bool = False
    promtail_reachable: bool = False
    scrape_target_health: str = "unknown"
    stale_metrics: bool = False
    readiness_reasons: list[str] = Field(default_factory=list)
    remediation: list[str] = Field(default_factory=list)
    technical_details: list[str] = Field(default_factory=list)
    component_failure_reasons: dict[str, str] = Field(default_factory=dict)
    last_validated_at: datetime | None = None
    last_successful_check_at: datetime | None = None
    collected_at: datetime


class MonitoringValidationAttemptRead(BaseModel):
    id: UUID
    server_id: UUID
    monitoring_snapshot_id: UUID | None = None
    audit_event_id: UUID | None = None
    validation_method: str
    component_results: dict[str, object] = Field(default_factory=dict)
    monitoring_state: str
    result: str
    failure_reason: str | None = None
    duration_ms: int | None = None
    started_at: datetime
    finished_at: datetime
    details: dict[str, object] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class MonitoringOverviewRead(BaseModel):
    total_servers: int
    online_servers: int
    offline_servers: int
    observable_servers: int = 0
    degraded_servers: int = 0
    monitored_servers: int = 0
    partial_servers: int = 0
    unmonitored_servers: int = 0
    stale_servers: int = 0
    unknown_servers: int = 0
    metrics_missing_servers: int = 0
    logs_missing_servers: int = 0
    stale_metrics_servers: int = 0
    providers: list[MonitoringProviderStatusRead]
    servers: list[ServerMetricsRead]


class PrometheusHealthRead(BaseModel):
    configured: bool
    reachable: bool
    error: str | None = None
    integration_id: UUID | None = None
    prometheus_url: str | None = None
    grafana_url: str | None = None
    loki_url: str | None = None
    providers: list[MonitoringProviderStatusRead] = Field(default_factory=list)


class MonitoringValidationRead(BaseModel):
    checked_servers: int
    updated_servers: int
    failed_servers: int = 0

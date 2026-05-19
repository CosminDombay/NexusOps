from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MonitoringMetricRead(BaseModel):
    name: str
    value: float | None = None
    unit: str


class ServerMetricsRead(BaseModel):
    server_id: UUID
    hostname: str
    ip_address: str
    online: bool
    cpu_usage_percent: float | None = None
    memory_usage_percent: float | None = None
    disk_usage_percent: float | None = None
    uptime_seconds: float | None = None
    grafana_url: str | None = None
    prometheus_url: str | None = None
    loki_url: str | None = None
    collected_at: datetime


class MonitoringOverviewRead(BaseModel):
    total_servers: int
    online_servers: int
    offline_servers: int
    servers: list[ServerMetricsRead]


class PrometheusHealthRead(BaseModel):
    configured: bool
    reachable: bool
    error: str | None = None
    prometheus_url: str | None = None
    grafana_url: str | None = None
    loki_url: str | None = None

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

from backend.app.modules.deployments.models import DeploymentStatus


@dataclass(frozen=True)
class DeploymentContainerState:
    service: str
    name: str
    state: str
    health: str = "unknown"
    uptime_seconds: int | None = None
    restart_count: int | None = None

    @property
    def is_running(self) -> bool:
        return self.state == "running"

    @property
    def is_unhealthy(self) -> bool:
        return self.health == "unhealthy"


@dataclass(frozen=True)
class DeploymentRuntimeState:
    target_server_id: UUID
    status: DeploymentStatus
    runtime_state: str
    sync_status: str
    health_state: str
    containers: list[DeploymentContainerState] = field(default_factory=list)
    missing_services: list[str] = field(default_factory=list)
    inspected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    error: str | None = None

    @property
    def is_drifted(self) -> bool:
        return self.sync_status == "drifted"


def expected_compose_services(compose_content: str) -> set[str]:
    services: set[str] = set()
    in_services = False
    services_indent = 0
    service_indent: int | None = None
    for line in compose_content.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        services_match = re.match(r"^(\s*)services:\s*$", line)
        if services_match:
            in_services = True
            services_indent = len(services_match.group(1))
            service_indent = None
            continue
        if in_services:
            indent = len(line) - len(line.lstrip(" "))
            if indent <= services_indent:
                break
            if line.lstrip().startswith("-"):
                continue
            if service_indent is None:
                service_indent = indent
            if indent != service_indent:
                continue
            match = re.match(r"^\s*([A-Za-z0-9_.-]+):\s*$", line)
            if match:
                services.add(match.group(1))
    return services


class DeploymentRuntimeInspector:
    """Parses live Docker/Compose inspection output into runtime state."""

    @classmethod
    def parse(
        cls,
        *,
        target_server_id: UUID,
        stdout: str,
        expected_services: set[str],
        desired_running: bool,
    ) -> DeploymentRuntimeState:
        if not stdout.strip():
            return cls._empty_state(target_server_id, expected_services, desired_running)

        containers = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            labels = item.get("Labels") or item.get("Config", {}).get("Labels") or {}
            state_payload = item.get("State") if isinstance(item.get("State"), dict) else {}
            service = str(item.get("Service") or labels.get("com.docker.compose.service") or item.get("Name") or "unknown")
            state = str(state_payload.get("Status") or item.get("State") or item.get("Status") or "unknown").lower()
            health_payload = state_payload.get("Health") if isinstance(state_payload.get("Health"), dict) else {}
            health = str(health_payload.get("Status") or item.get("Health") or item.get("HealthStatus") or "unknown").lower()
            containers.append(
                DeploymentContainerState(
                    service=service,
                    name=str(item.get("Name") or item.get("Names") or service),
                    state=cls._normalize_state(state),
                    health=health if health not in {"", "none"} else "unknown",
                    uptime_seconds=cls._uptime_seconds(item, state_payload),
                    restart_count=cls._restart_count(item, state_payload),
                )
            )

        if not containers:
            return cls._empty_state(target_server_id, expected_services, desired_running)
        return cls._state_from_containers(target_server_id, containers, expected_services, desired_running)

    @classmethod
    def failed(
        cls,
        *,
        target_server_id: UUID,
        error: str,
        expected_services: set[str],
        desired_running: bool,
    ) -> DeploymentRuntimeState:
        base = cls._empty_state(target_server_id, expected_services, desired_running)
        return DeploymentRuntimeState(
            target_server_id=target_server_id,
            status=DeploymentStatus.DEGRADED if desired_running else DeploymentStatus.STOPPED,
            runtime_state="unknown",
            sync_status="unknown",
            health_state="unknown",
            containers=[],
            missing_services=sorted(expected_services),
            error=error,
        )

    @classmethod
    def _empty_state(
        cls,
        target_server_id: UUID,
        expected_services: set[str],
        desired_running: bool,
    ) -> DeploymentRuntimeState:
        runtime_state = "missing" if expected_services else "unknown"
        return DeploymentRuntimeState(
            target_server_id=target_server_id,
            status=DeploymentStatus.DEGRADED if desired_running else DeploymentStatus.STOPPED,
            runtime_state=runtime_state,
            sync_status="drifted" if desired_running and expected_services else "synced",
            health_state="unhealthy" if desired_running and expected_services else "unknown",
            missing_services=sorted(expected_services),
        )

    @classmethod
    def _state_from_containers(
        cls,
        target_server_id: UUID,
        containers: list[DeploymentContainerState],
        expected_services: set[str],
        desired_running: bool,
    ) -> DeploymentRuntimeState:
        present = {container.service for container in containers}
        missing = sorted(expected_services - present)
        running = [container for container in containers if container.is_running]
        stopped = [container for container in containers if not container.is_running]
        unhealthy = [container for container in containers if container.is_unhealthy]

        if desired_running:
            if missing or stopped or unhealthy:
                runtime_state = "degraded" if running else "stopped"
                status = DeploymentStatus.DEGRADED if running else DeploymentStatus.STOPPED
                health_state = "degraded" if running else "unhealthy"
                sync_status = "drifted"
            else:
                runtime_state = "running"
                status = DeploymentStatus.RUNNING
                health_state = "healthy"
                sync_status = "synced"
        else:
            runtime_state = "stopped" if not running else "running"
            status = DeploymentStatus.STOPPED if not running else DeploymentStatus.DEGRADED
            health_state = "stopped" if not running else "degraded"
            sync_status = "synced" if not running else "drifted"

        return DeploymentRuntimeState(
            target_server_id=target_server_id,
            status=status,
            runtime_state=runtime_state,
            sync_status=sync_status,
            health_state=health_state,
            containers=containers,
            missing_services=missing,
        )

    @staticmethod
    def _normalize_state(value: str) -> str:
        if "running" in value or value == "up":
            return "running"
        if "exit" in value or "exited" in value:
            return "exited"
        if "stop" in value:
            return "stopped"
        if "dead" in value:
            return "dead"
        return value or "unknown"

    @staticmethod
    def _restart_count(item: dict, state_payload: dict | None = None) -> int | None:
        raw = item.get("RestartCount")
        if raw is None and state_payload:
            raw = state_payload.get("Restarting")
        if isinstance(raw, int):
            return raw
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _uptime_seconds(item: dict, state_payload: dict | None = None) -> int | None:
        started_at = item.get("StartedAt") or (state_payload or {}).get("StartedAt")
        if not started_at:
            return None
        try:
            parsed = datetime.fromisoformat(str(started_at).replace("Z", "+00:00"))
        except ValueError:
            return None
        return max(0, int((datetime.now(UTC) - parsed).total_seconds()))

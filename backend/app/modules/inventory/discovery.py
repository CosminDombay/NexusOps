from __future__ import annotations

import csv
import shlex
from collections.abc import Iterable
from dataclasses import dataclass
from io import StringIO

from backend.app.adapters.ssh.base import SshAdapter
from backend.app.adapters.ssh.host_keys import HostKeyPolicy
from backend.app.adapters.ssh.paramiko import SshConnectionError
from backend.app.adapters.ssh.sudo import prepare_sudo_command
from backend.app.modules.credentials.service import CredentialNotFoundError, CredentialService
from backend.app.modules.inventory.models import Server, ServerSshAuthMethod
from backend.app.modules.inventory.schemas import (
    DockerContainerRead,
    DockerNetworkRead,
    HostDockerRead,
    HostFilesystemRead,
    HostNetworkInterfaceRead,
    HostNetworkRead,
    HostSystemRead,
    ListeningPortRead,
)


class HostDiscoveryError(Exception):
    """Raised when a host cannot be inspected over SSH."""


@dataclass(frozen=True)
class _CommandSpec:
    name: str
    command: str


class HostDiscoveryService:
    """Read-only Linux host discovery over the existing SSH boundary."""

    def __init__(
        self,
        ssh_adapter: SshAdapter,
        *,
        credential_service: CredentialService | None = None,
    ) -> None:
        self.ssh_adapter = ssh_adapter
        self.credential_service = credential_service

    async def system(self, server: Server) -> HostSystemRead:
        sections = await self._run_sections(
            server,
            [
                _CommandSpec("hostname", "hostname 2>/dev/null || true"),
                _CommandSpec("kernel", "uname -srmo 2>/dev/null || uname -a 2>/dev/null || true"),
                _CommandSpec(
                    "os",
                    ". /etc/os-release 2>/dev/null && printf '%s' \"${PRETTY_NAME:-$NAME}\" || hostnamectl 2>/dev/null | sed -n 's/^ *Operating System: //p'",
                ),
                _CommandSpec("uptime", "cat /proc/uptime 2>/dev/null | awk '{print int($1)}' || true"),
                _CommandSpec("load", "cat /proc/loadavg 2>/dev/null | awk '{print $1,$2,$3}' || true"),
                _CommandSpec("cpu", "lscpu 2>/dev/null || true"),
                _CommandSpec("memory", "free -b 2>/dev/null || true"),
                _CommandSpec("filesystems", "df -B1 -P -T 2>/dev/null || df -P -T 2>/dev/null || true"),
            ],
        )
        memory = _parse_free(sections.get("memory", ""))
        return HostSystemRead(
            hostname=_first_line(sections.get("hostname")) or server.hostname,
            operating_system=_first_line(sections.get("os")) or server.operating_system,
            kernel=_first_line(sections.get("kernel")),
            uptime_seconds=_optional_int(_first_line(sections.get("uptime"))),
            load_average=_parse_load(sections.get("load", "")),
            cpu_model=_cpu_value(sections.get("cpu", ""), "Model name"),
            cpu_cores=_optional_int(_cpu_value(sections.get("cpu", ""), "CPU(s)")),
            memory_total_bytes=memory.get("total"),
            memory_used_bytes=memory.get("used"),
            memory_available_bytes=memory.get("available"),
            filesystems=_parse_filesystems(sections.get("filesystems", "")),
        )

    async def network(self, server: Server) -> HostNetworkRead:
        sections = await self._run_sections(
            server,
            [
                _CommandSpec("interfaces", "ip -o addr show 2>/dev/null || true"),
                _CommandSpec("ports", "ss -tulpnH 2>/dev/null || netstat -tulpn 2>/dev/null || true"),
            ],
        )
        return HostNetworkRead(
            lan_ip=server.ip_address,
            tailscale_ip=None,
            interfaces=_parse_interfaces(sections.get("interfaces", "")),
            listening_ports=_parse_ports(sections.get("ports", "")),
        )

    async def docker(self, server: Server) -> HostDockerRead:
        sections = await self._run_sections(
            server,
            [
                _CommandSpec("docker_access", _docker_sudo_fallback_function()),
                _CommandSpec(
                    "version",
                    "nexusops_docker version --format '{{.Server.Version}}' 2>/dev/null || true",
                ),
                _CommandSpec(
                    "containers",
                    "nexusops_docker ps --format '{{.ID}},{{.Names}},{{.Image}},{{.Status}},{{.Ports}},{{.Label \"com.docker.compose.project\"}}' 2>/dev/null || true",
                ),
                _CommandSpec(
                    "networks",
                    "nexusops_docker network ls --format '{{.Name}},{{.Driver}},{{.Scope}}' 2>/dev/null || true",
                ),
            ],
        )
        version = _first_line(sections.get("version"))
        return HostDockerRead(
            installed=bool(version),
            version=version,
            containers=_parse_containers(sections.get("containers", "")),
            networks=_parse_networks(sections.get("networks", "")),
        )

    async def _run_sections(self, server: Server, specs: Iterable[_CommandSpec]) -> dict[str, str]:
        command = _sectioned_command(specs)
        ssh_user = server.ssh_username
        ssh_password = server.ssh_password if server.ssh_auth_method == ServerSshAuthMethod.PASSWORD else None
        ssh_private_key_path = (
            server.ssh_private_key_path if server.ssh_auth_method == ServerSshAuthMethod.KEY else None
        )
        ssh_private_key: str | None = None
        ssh_passphrase: str | None = None

        if server.credential_id is not None:
            if self.credential_service is None:
                raise HostDiscoveryError("Credential service is required for credential-backed host discovery")
            try:
                credential = await self.credential_service.resolve_credential(server.credential_id)
            except CredentialNotFoundError as exc:
                raise HostDiscoveryError("Configured SSH credential was not found") from exc
            ssh_user = credential.username or ssh_user
            if credential.credential_type in {"password", "ssh_password"}:
                ssh_password = credential.secret
                ssh_private_key_path = None
            elif credential.credential_type == "ssh_key":
                ssh_password = None
                ssh_private_key_path = None
                ssh_private_key = credential.private_key
                ssh_passphrase = credential.passphrase

        command, input_data = prepare_sudo_command(command, ssh_password)

        host_key_policy = HostKeyPolicy.for_server(server)
        try:
            result = await self.ssh_adapter.run_command(
                host=server.ip_address,
                port=server.ssh_port,
                user=ssh_user,
                password=ssh_password,
                private_key_path=ssh_private_key_path,
                private_key=ssh_private_key,
                passphrase=ssh_passphrase,
                command=command,
                input_data=input_data,
                host_key_policy=host_key_policy,
            )
        except SshConnectionError as exc:
            raise HostDiscoveryError(str(exc)) from exc
        host_key_policy.persist_to(server)

        if result.exit_code != 0 and not result.stdout:
            raise HostDiscoveryError(result.stderr or "Host discovery command failed")
        return _split_sections(result.stdout)


def _sectioned_command(specs: Iterable[_CommandSpec]) -> str:
    parts = ["set +e"]
    for spec in specs:
        label = shlex.quote(spec.name)
        parts.append(f"printf '\\n__NEXUSOPS_SECTION__:%s\\n' {label}")
        parts.append(spec.command)
    return "\n".join(parts)


def _docker_sudo_fallback_function() -> str:
    return "\n".join(
        [
            "nexusops_docker() {",
            "  err_file=$(mktemp)",
            "  if docker \"$@\" 2>\"$err_file\"; then rm -f \"$err_file\"; return 0; fi",
            "  status=$?",
            "  if grep -qiE 'permission denied|cannot connect to the docker daemon|docker.sock|dial unix' \"$err_file\"; then",
            "    sudo_err_file=$(mktemp)",
            "    if sudo docker \"$@\" 2>\"$sudo_err_file\"; then rm -f \"$err_file\" \"$sudo_err_file\"; return 0; fi",
            "    sudo_status=$?",
            "    cat \"$err_file\" >&2",
            "    cat \"$sudo_err_file\" >&2",
            "    rm -f \"$err_file\" \"$sudo_err_file\"",
            "    return \"$sudo_status\"",
            "  fi",
            "  cat \"$err_file\" >&2",
            "  rm -f \"$err_file\"",
            "  return \"$status\"",
            "}",
        ]
    )


def _split_sections(output: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in output.splitlines():
        if line.startswith("__NEXUSOPS_SECTION__:"):
            current = line.split(":", 1)[1].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def _first_line(value: str | None) -> str | None:
    if not value:
        return None
    for line in value.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _optional_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_load(value: str) -> list[float]:
    result = []
    for item in value.split()[:3]:
        try:
            result.append(float(item))
        except ValueError:
            continue
    return result


def _cpu_value(output: str, key: str) -> str | None:
    prefix = f"{key}:"
    for line in output.splitlines():
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return None


def _parse_free(output: str) -> dict[str, int | None]:
    for line in output.splitlines():
        if line.lower().startswith("mem:"):
            parts = line.split()
            return {
                "total": _optional_int(parts[1]) if len(parts) > 1 else None,
                "used": _optional_int(parts[2]) if len(parts) > 2 else None,
                "available": _optional_int(parts[6]) if len(parts) > 6 else None,
            }
    return {"total": None, "used": None, "available": None}


def _parse_filesystems(output: str) -> list[HostFilesystemRead]:
    filesystems = []
    for line in output.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 7:
            continue
        filesystems.append(
            HostFilesystemRead(
                filesystem=parts[0],
                type=parts[1],
                size_bytes=_optional_int(parts[2]),
                used_bytes=_optional_int(parts[3]),
                available_bytes=_optional_int(parts[4]),
                mountpoint=parts[6],
            )
        )
    return filesystems


def _parse_interfaces(output: str) -> list[HostNetworkInterfaceRead]:
    interfaces: dict[str, HostNetworkInterfaceRead] = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        name = parts[1]
        family = parts[2]
        address = parts[3]
        item = interfaces.setdefault(name, HostNetworkInterfaceRead(name=name, addresses=[]))
        item.addresses.append(address if family != "inet6" else address)
    return list(interfaces.values())


def _parse_ports(output: str) -> list[ListeningPortRead]:
    ports = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 5 or parts[0].lower().startswith(("proto", "active")):
            continue
        protocol = parts[0].lower()
        local = parts[4] if protocol in {"tcp", "udp", "tcp6", "udp6"} else parts[3]
        process = parts[-1] if len(parts) > 6 else None
        port = _port_from_address(local)
        if port is None:
            continue
        ports.append(
            ListeningPortRead(
                protocol=protocol.replace("6", ""),
                address=local,
                port=port,
                process=None if process == "-" else process,
                service=_service_name(port),
            )
        )
    return ports


def _port_from_address(value: str) -> int | None:
    candidate = value.rsplit(":", 1)[-1]
    return _optional_int(candidate)


def _service_name(port: int) -> str | None:
    common = {22: "ssh", 80: "http", 443: "https", 3000: "node", 5432: "postgres", 8000: "api", 9090: "prometheus"}
    return common.get(port)


def _parse_containers(output: str) -> list[DockerContainerRead]:
    containers = []
    reader = csv.reader(StringIO(output))
    for row in reader:
        if len(row) < 6:
            continue
        containers.append(
            DockerContainerRead(
                container_id=row[0],
                name=row[1],
                image=row[2],
                status=row[3],
                ports=row[4],
                compose_project=row[5] or None,
            )
        )
    return containers


def _parse_networks(output: str) -> list[DockerNetworkRead]:
    networks = []
    reader = csv.reader(StringIO(output))
    for row in reader:
        if len(row) < 3:
            continue
        networks.append(DockerNetworkRead(name=row[0], driver=row[1], scope=row[2]))
    return networks

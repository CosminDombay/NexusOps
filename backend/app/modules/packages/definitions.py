from dataclasses import dataclass


@dataclass(frozen=True)
class PackageDefinition:
    id: str
    name: str
    category: str
    supported_os: list[str]
    install_command: str
    uninstall_command: str
    validation_command: str
    variables: list[dict]
    tags: list[str]
    description: str


PACKAGE_REGISTRY: tuple[PackageDefinition, ...] = (
    PackageDefinition(
        id="docker-engine",
        name="Docker Engine",
        category="Containers",
        supported_os=["ubuntu", "debian"],
        install_command=(
            "curl -fsSL https://get.docker.com -o /tmp/get-docker.sh "
            "&& sudo sh /tmp/get-docker.sh"
        ),
        uninstall_command="sudo apt-get remove -y docker-ce docker-ce-cli containerd.io || true",
        validation_command="docker --version && systemctl is-active docker",
        variables=[{"name": "docker_data_path", "description": "Docker data root path", "default_value": "/var/lib/docker", "required": False, "sensitive": False}],
        tags=["containers", "runtime"],
        description="Docker runtime for containerized workloads.",
    ),
    PackageDefinition(
        id="tailscale",
        name="Tailscale",
        category="Networking",
        supported_os=["ubuntu", "debian", "rocky", "fedora"],
        install_command="curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up --auth-key {{ tailscale_auth_key }}",
        uninstall_command="sudo tailscale down || true",
        validation_command="tailscale version",
        variables=[{"name": "tailscale_auth_key", "description": "Tailscale reusable auth key", "default_value": None, "required": True, "sensitive": True}],
        tags=["vpn", "mesh", "networking"],
        description="Tailscale mesh networking client.",
    ),
    PackageDefinition(
        id="node-exporter",
        name="Node Exporter",
        category="Monitoring",
        supported_os=["ubuntu", "debian"],
        install_command="sudo apt-get update && sudo apt-get install -y prometheus-node-exporter",
        uninstall_command="sudo apt-get remove -y prometheus-node-exporter || true",
        validation_command="systemctl is-active prometheus-node-exporter",
        variables=[],
        tags=["monitoring", "prometheus", "metrics"],
        description="Prometheus exporter for host metrics.",
    ),
    PackageDefinition(
        id="promtail",
        name="Promtail",
        category="Monitoring",
        supported_os=["ubuntu", "debian"],
        install_command="echo 'Promtail package definition requires repository setup before install'",
        uninstall_command="sudo systemctl stop promtail || true",
        validation_command="promtail --version",
        variables=[{"name": "grafana_url", "description": "Grafana or Loki endpoint URL", "default_value": None, "required": False, "sensitive": False}],
        tags=["monitoring", "logs", "loki"],
        description="Log shipping agent for Loki. Repository setup is intentionally deferred.",
    ),
    PackageDefinition(
        id="fail2ban",
        name="Fail2Ban",
        category="Security",
        supported_os=["ubuntu", "debian"],
        install_command="sudo apt-get update && sudo apt-get install -y fail2ban",
        uninstall_command="sudo apt-get remove -y fail2ban || true",
        validation_command="systemctl is-active fail2ban",
        variables=[],
        tags=["security", "ssh", "hardening"],
        description="Basic intrusion prevention for SSH and common services.",
    ),
    PackageDefinition(
        id="ufw",
        name="UFW",
        category="Security",
        supported_os=["ubuntu", "debian"],
        install_command="sudo apt-get update && sudo apt-get install -y ufw",
        uninstall_command="sudo apt-get remove -y ufw || true",
        validation_command="ufw status",
        variables=[],
        tags=["security", "firewall"],
        description="Uncomplicated Firewall package and status tooling.",
    ),
)


def list_package_definitions() -> list[PackageDefinition]:
    return list(PACKAGE_REGISTRY)


def get_package_definition(package_id: str) -> PackageDefinition | None:
    return next((package for package in PACKAGE_REGISTRY if package.id == package_id), None)

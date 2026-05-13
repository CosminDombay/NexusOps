from dataclasses import dataclass


@dataclass(frozen=True)
class PackageDefinition:
    id: str
    name: str
    category: str
    supported_os: list[str]
    install_command: str
    validation_command: str
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
        validation_command="docker --version && systemctl is-active docker",
        tags=["containers", "runtime"],
        description="Docker runtime for containerized workloads.",
    ),
    PackageDefinition(
        id="tailscale",
        name="Tailscale",
        category="Networking",
        supported_os=["ubuntu", "debian", "rocky", "fedora"],
        install_command="curl -fsSL https://tailscale.com/install.sh | sh",
        validation_command="tailscale version",
        tags=["vpn", "mesh", "networking"],
        description="Tailscale mesh networking client.",
    ),
    PackageDefinition(
        id="node-exporter",
        name="Node Exporter",
        category="Monitoring",
        supported_os=["ubuntu", "debian"],
        install_command="sudo apt-get update && sudo apt-get install -y prometheus-node-exporter",
        validation_command="systemctl is-active prometheus-node-exporter",
        tags=["monitoring", "prometheus", "metrics"],
        description="Prometheus exporter for host metrics.",
    ),
    PackageDefinition(
        id="promtail",
        name="Promtail",
        category="Monitoring",
        supported_os=["ubuntu", "debian"],
        install_command="echo 'Promtail package definition requires repository setup before install'",
        validation_command="promtail --version",
        tags=["monitoring", "logs", "loki"],
        description="Log shipping agent for Loki. Repository setup is intentionally deferred.",
    ),
    PackageDefinition(
        id="fail2ban",
        name="Fail2Ban",
        category="Security",
        supported_os=["ubuntu", "debian"],
        install_command="sudo apt-get update && sudo apt-get install -y fail2ban",
        validation_command="systemctl is-active fail2ban",
        tags=["security", "ssh", "hardening"],
        description="Basic intrusion prevention for SSH and common services.",
    ),
    PackageDefinition(
        id="ufw",
        name="UFW",
        category="Security",
        supported_os=["ubuntu", "debian"],
        install_command="sudo apt-get update && sudo apt-get install -y ufw",
        validation_command="ufw status",
        tags=["security", "firewall"],
        description="Uncomplicated Firewall package and status tooling.",
    ),
)


def list_package_definitions() -> list[PackageDefinition]:
    return list(PACKAGE_REGISTRY)


def get_package_definition(package_id: str) -> PackageDefinition | None:
    return next((package for package in PACKAGE_REGISTRY if package.id == package_id), None)

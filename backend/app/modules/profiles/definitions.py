from dataclasses import dataclass


@dataclass(frozen=True)
class ProfileStep:
    id: str
    name: str
    kind: str
    reference_id: str


@dataclass(frozen=True)
class InfrastructureProfile:
    id: str
    name: str
    category: str
    description: str
    tags: list[str]
    steps: list[ProfileStep]


PROFILE_REGISTRY: tuple[InfrastructureProfile, ...] = (
    InfrastructureProfile(
        id="base-linux-server",
        name="Base Linux Server",
        category="Baseline",
        description="Basic diagnostics and host hardening package definitions for a managed Linux server.",
        tags=["baseline", "linux", "security"],
        steps=[
            ProfileStep(
                id="check-uptime",
                name="Check uptime",
                kind="action",
                reference_id="check-uptime",
            ),
            ProfileStep(
                id="install-fail2ban",
                name="Install Fail2Ban",
                kind="package",
                reference_id="fail2ban",
            ),
            ProfileStep(id="install-ufw", name="Install UFW", kind="package", reference_id="ufw"),
        ],
    ),
    InfrastructureProfile(
        id="docker-host",
        name="Docker Host",
        category="Containers",
        description="Prepare a Linux host for Docker workloads and verify Docker service state.",
        tags=["docker", "containers", "runtime"],
        steps=[
            ProfileStep(
                id="install-docker",
                name="Install Docker Engine",
                kind="package",
                reference_id="docker-engine",
            ),
            ProfileStep(
                id="docker-status",
                name="Check Docker Service",
                kind="action",
                reference_id="docker-status",
            ),
            ProfileStep(
                id="check-docker-containers",
                name="Check Docker Containers",
                kind="action",
                reference_id="check-docker-containers",
            ),
        ],
    ),
    InfrastructureProfile(
        id="monitoring-node",
        name="Monitoring Node",
        category="Monitoring",
        description="Install host monitoring and log shipping definitions for observability nodes.",
        tags=["monitoring", "metrics", "logs"],
        steps=[
            ProfileStep(
                id="install-node-exporter",
                name="Install Node Exporter",
                kind="package",
                reference_id="node-exporter",
            ),
            ProfileStep(
                id="install-promtail",
                name="Install Promtail",
                kind="package",
                reference_id="promtail",
            ),
            ProfileStep(
                id="check-memory",
                name="Check Memory Usage",
                kind="action",
                reference_id="check-memory-usage",
            ),
        ],
    ),
    InfrastructureProfile(
        id="development-vm",
        name="Development VM",
        category="Development",
        description="Prepare a VM with container runtime, mesh networking, and basic diagnostics.",
        tags=["development", "docker", "networking"],
        steps=[
            ProfileStep(
                id="install-docker",
                name="Install Docker Engine",
                kind="package",
                reference_id="docker-engine",
            ),
            ProfileStep(
                id="install-tailscale",
                name="Install Tailscale",
                kind="package",
                reference_id="tailscale",
            ),
            ProfileStep(
                id="check-disk",
                name="Check Disk Usage",
                kind="action",
                reference_id="check-disk-usage",
            ),
        ],
    ),
)


def list_profiles() -> list[InfrastructureProfile]:
    return list(PROFILE_REGISTRY)


def get_profile(profile_id: str) -> InfrastructureProfile | None:
    return next((profile for profile in PROFILE_REGISTRY if profile.id == profile_id), None)

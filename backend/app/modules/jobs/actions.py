from dataclasses import dataclass


@dataclass(frozen=True)
class OperationalAction:
    id: str
    name: str
    category: str
    description: str
    command: str
    destructive: bool = False


ACTION_REGISTRY: tuple[OperationalAction, ...] = (
    OperationalAction(
        id="check-uptime",
        name="Check System Uptime",
        category="Diagnostics",
        description="Show host uptime, load average, and logged-in users.",
        command="uptime",
    ),
    OperationalAction(
        id="check-disk-usage",
        name="Check Disk Usage",
        category="Diagnostics",
        description="Inspect filesystem usage with human-readable sizes.",
        command="df -h",
    ),
    OperationalAction(
        id="check-memory-usage",
        name="Check Memory Usage",
        category="Diagnostics",
        description="Inspect memory usage in megabytes.",
        command="free -m",
    ),
    OperationalAction(
        id="check-docker-containers",
        name="Check Docker Containers",
        category="Diagnostics",
        description="List Docker containers on the target host.",
        command="docker ps",
    ),
    OperationalAction(
        id="validation:sudo-ready",
        name="Validate Sudo Readiness",
        category="Validation",
        description="Confirm the SSH user can run sudo through the selected execution credential.",
        command="sudo true && echo sudo-ready",
    ),
    OperationalAction(
        id="docker-status",
        name="Check Docker Service",
        category="Service Operations",
        description="Check Docker service status through systemd.",
        command="systemctl status docker --no-pager",
    ),
    OperationalAction(
        id="restart-docker",
        name="Restart Docker Service",
        category="Service Operations",
        description="Restart the Docker systemd service.",
        command="sudo systemctl restart docker && systemctl status docker --no-pager",
        destructive=True,
    ),
    OperationalAction(
        id="install-docker",
        name="Install Docker Engine",
        category="Installation",
        description="Install Docker Engine using the official convenience script.",
        command=(
            "curl -fsSL https://get.docker.com -o /tmp/get-docker.sh "
            "&& sudo sh /tmp/get-docker.sh"
        ),
        destructive=True,
    ),
    OperationalAction(
        id="install-tailscale",
        name="Install Tailscale",
        category="Installation",
        description="Install Tailscale using the official install script.",
        command="curl -fsSL https://tailscale.com/install.sh | sh",
        destructive=True,
    ),
    OperationalAction(
        id="install-node-exporter",
        name="Install Node Exporter",
        category="Installation",
        description="Install Node Exporter package when available through apt.",
        command=(
            "sudo apt-get update "
            "&& sudo apt-get install -y prometheus-node-exporter "
            "&& systemctl status prometheus-node-exporter --no-pager"
        ),
        destructive=True,
    ),
)


def list_actions() -> list[OperationalAction]:
    return list(ACTION_REGISTRY)


def get_action(action_id: str) -> OperationalAction | None:
    return next((action for action in ACTION_REGISTRY if action.id == action_id), None)

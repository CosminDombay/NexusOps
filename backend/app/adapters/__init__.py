"""Infrastructure adapter contracts and implementations."""
from backend.app.adapters.base import Adapter
from backend.app.adapters.docker import DockerComposeAdapter
from backend.app.adapters.proxmox import HttpProxmoxAdapter, ProxmoxAdapter
from backend.app.adapters.ssh import SshAdapter, SshExecutionResult

__all__ = [
    "Adapter",
    "DockerComposeAdapter",
    "HttpProxmoxAdapter",
    "ProxmoxAdapter",
    "SshAdapter",
    "SshExecutionResult",
]

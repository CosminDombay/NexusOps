from typing import Any
from urllib.parse import quote, urljoin

import httpx
import structlog

from backend.app.adapters.proxmox.base import ProxmoxAdapter
from backend.app.core.config import settings

logger = structlog.get_logger(__name__)


class ProxmoxAdapterError(Exception):
    """Base exception for Proxmox adapter failures."""


class ProxmoxConfigurationError(ProxmoxAdapterError):
    """Raised when required Proxmox settings are missing."""


class ProxmoxConnectionError(ProxmoxAdapterError):
    """Raised when Proxmox cannot be reached or rejects the request."""


class HttpProxmoxAdapter(ProxmoxAdapter):
    """Async HTTP implementation for read-only Proxmox API discovery."""

    @property
    def name(self) -> str:
        return "proxmox-http"

    def __init__(
        self,
        *,
        api_url: str | None = None,
        token_id: str | None = None,
        token_secret: str | None = None,
        verify_ssl: bool | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.api_url = (api_url or settings.proxmox_api_url or "").rstrip("/") + "/"
        self.token_id = token_id if token_id is not None else settings.proxmox_token_id
        self.token_secret = (
            token_secret if token_secret is not None else settings.proxmox_token_secret
        )
        self.verify_ssl = settings.proxmox_verify_ssl if verify_ssl is None else verify_ssl
        self.timeout_seconds = timeout_seconds or settings.proxmox_timeout_seconds

    async def get_nodes(self) -> list[dict[str, Any]]:
        data = await self._get("nodes")
        return list(data)

    async def list_vms(self) -> list[dict[str, Any]]:
        data = await self._get("cluster/resources", params={"type": "vm"})
        return list(data)

    async def list_vm_templates(self) -> list[dict[str, Any]]:
        vms = await self.list_vms()
        return [vm for vm in vms if bool(vm.get("template"))]

    async def get_vm_status(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        normalized_type = self._normalize_vm_type(vm_type)
        return dict(await self._get(f"nodes/{node}/{normalized_type}/{vm_id}/status/current"))

    async def get_vm_network_interfaces(self, *, node: str, vm_id: int, vm_type: str) -> list[dict[str, Any]]:
        normalized_type = self._normalize_vm_type(vm_type)
        if normalized_type != "qemu":
            return []
        try:
            data = await self._get(f"nodes/{node}/qemu/{vm_id}/agent/network-get-interfaces")
        except ProxmoxConnectionError:
            return []
        if isinstance(data, dict) and isinstance(data.get("result"), list):
            return list(data["result"])
        if isinstance(data, list):
            return data
        return []

    async def get_cluster_summary(self) -> dict[str, Any]:
        resources = await self._get("cluster/resources")
        return {"resources": list(resources)}

    async def get_task_status(self, *, node: str, task_id: str) -> dict[str, Any]:
        quoted_task_id = quote(task_id, safe="")
        return dict(await self._get(f"nodes/{node}/tasks/{quoted_task_id}/status"))

    async def start_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        return await self._post_vm_action(node=node, vm_id=vm_id, vm_type=vm_type, action="start")

    async def stop_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        return await self._post_vm_action(node=node, vm_id=vm_id, vm_type=vm_type, action="stop")

    async def reboot_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        return await self._post_vm_action(node=node, vm_id=vm_id, vm_type=vm_type, action="reboot")

    async def shutdown_vm(self, *, node: str, vm_id: int, vm_type: str) -> dict[str, Any]:
        return await self._post_vm_action(
            node=node,
            vm_id=vm_id,
            vm_type=vm_type,
            action="shutdown",
        )

    async def clone_vm_template(
        self,
        *,
        node: str,
        template_id: int,
        new_vm_id: int,
        name: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str] = {
            "newid": str(new_vm_id),
            "name": name,
            "full": "1",
        }
        if description:
            params["description"] = description
        data = await self._post(f"nodes/{node}/qemu/{template_id}/clone", data=params)
        return {"task_id": data}

    async def configure_cloud_init(
        self,
        *,
        node: str,
        vm_id: int,
        cpu_cores: int,
        memory_mb: int,
        network_bridge: str,
        username: str,
        password: str | None,
        ssh_public_key: str | None,
        ip_cidr: str,
        gateway: str,
        dns_servers: list[str],
        start_on_boot: bool,
        description: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str] = {
            "cores": str(cpu_cores),
            "memory": str(memory_mb),
            "net0": f"virtio,bridge={network_bridge}",
            "ciuser": username,
            "ipconfig0": f"ip={ip_cidr},gw={gateway}",
            "onboot": "1" if start_on_boot else "0",
        }
        if password:
            params["cipassword"] = password
        if ssh_public_key:
            params["sshkeys"] = ssh_public_key
        if dns_servers:
            params["nameserver"] = " ".join(dns_servers)
        if description:
            params["description"] = description
        data = await self._put(f"nodes/{node}/qemu/{vm_id}/config", data=params)
        return {"task_id": data}

    async def resize_vm_disk(
        self,
        *,
        node: str,
        vm_id: int,
        disk_size_gb: int,
    ) -> dict[str, Any]:
        data = await self._put(
            f"nodes/{node}/qemu/{vm_id}/resize",
            data={"disk": "scsi0", "size": f"{disk_size_gb}G"},
        )
        return {"task_id": data}

    async def add_vm_disk(
        self,
        *,
        node: str,
        vm_id: int,
        disk: str,
        storage: str,
        size_gb: int,
    ) -> dict[str, Any]:
        data = await self._put(
            f"nodes/{node}/qemu/{vm_id}/config",
            data={disk: f"{storage}:{size_gb}"},
        )
        return {"task_id": data}

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:
        self._validate_configuration()
        url = urljoin(self.api_url, path.lstrip("/"))

        try:
            async with httpx.AsyncClient(
                headers=self._headers(),
                timeout=self.timeout_seconds,
                verify=self.verify_ssl,
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "proxmox_request_failed",
                url=url,
                status_code=exc.response.status_code,
                reason="http_status",
            )
            raise ProxmoxConnectionError(
                f"Proxmox API returned status {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("proxmox_request_failed", url=url, reason=exc.__class__.__name__)
            raise ProxmoxConnectionError("Unable to reach the configured Proxmox API") from exc

        payload = response.json()
        if not isinstance(payload, dict) or "data" not in payload:
            logger.warning("proxmox_response_invalid", url=url)
            raise ProxmoxConnectionError("Proxmox API returned an unexpected response shape")

        logger.info("proxmox_request_succeeded", url=url)
        return payload["data"]

    async def _post_vm_action(
        self,
        *,
        node: str,
        vm_id: int,
        vm_type: str,
        action: str,
    ) -> dict[str, Any]:
        normalized_type = self._normalize_vm_type(vm_type)
        data = await self._post(f"nodes/{node}/{normalized_type}/{vm_id}/status/{action}")
        return {"task_id": data}

    async def _post(self, path: str, data: dict[str, str] | None = None) -> Any:
        self._validate_configuration()
        url = urljoin(self.api_url, path.lstrip("/"))

        try:
            async with httpx.AsyncClient(
                headers=self._headers(),
                timeout=self.timeout_seconds,
                verify=self.verify_ssl,
            ) as client:
                response = await client.post(url, data=data)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "proxmox_request_failed",
                url=url,
                status_code=exc.response.status_code,
                reason="http_status",
            )
            raise ProxmoxConnectionError(
                f"Proxmox API returned status {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("proxmox_request_failed", url=url, reason=exc.__class__.__name__)
            raise ProxmoxConnectionError("Unable to reach the configured Proxmox API") from exc

        payload = response.json()
        if not isinstance(payload, dict) or "data" not in payload:
            logger.warning("proxmox_response_invalid", url=url)
            raise ProxmoxConnectionError("Proxmox API returned an unexpected response shape")

        logger.info("proxmox_request_succeeded", url=url)
        return payload["data"]

    async def _put(self, path: str, data: dict[str, str] | None = None) -> Any:
        self._validate_configuration()
        url = urljoin(self.api_url, path.lstrip("/"))

        try:
            async with httpx.AsyncClient(
                headers=self._headers(),
                timeout=self.timeout_seconds,
                verify=self.verify_ssl,
            ) as client:
                response = await client.put(url, data=data)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "proxmox_request_failed",
                url=url,
                status_code=exc.response.status_code,
                reason="http_status",
            )
            raise ProxmoxConnectionError(
                f"Proxmox API returned status {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            logger.warning("proxmox_request_failed", url=url, reason=exc.__class__.__name__)
            raise ProxmoxConnectionError("Unable to reach the configured Proxmox API") from exc

        payload = response.json()
        if not isinstance(payload, dict) or "data" not in payload:
            logger.warning("proxmox_response_invalid", url=url)
            raise ProxmoxConnectionError("Proxmox API returned an unexpected response shape")

        logger.info("proxmox_request_succeeded", url=url)
        return payload["data"]

    def _validate_configuration(self) -> None:
        missing = []
        if not self.api_url.strip("/"):
            missing.append("PROXMOX_API_URL")
        if not self.token_id:
            missing.append("PROXMOX_TOKEN_ID")
        if not self.token_secret:
            missing.append("PROXMOX_TOKEN_SECRET")

        if missing:
            logger.warning("proxmox_configuration_missing", missing=missing)
            raise ProxmoxConfigurationError(
                f"Missing Proxmox configuration: {', '.join(missing)}"
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"PVEAPIToken={self.token_id}={self.token_secret}",
            "Accept": "application/json",
        }

    @staticmethod
    def _normalize_vm_type(vm_type: str) -> str:
        if vm_type in {"qemu", "lxc"}:
            return vm_type
        if vm_type == "vm":
            return "qemu"
        raise ProxmoxConfigurationError("VM type must be qemu or lxc")

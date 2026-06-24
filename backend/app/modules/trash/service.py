from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.common.constants import InventoryLifecycleState
from backend.app.modules.automations.models import Automation, AutomationOperationType
from backend.app.modules.credentials.models import Credential
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialInUseError, CredentialNotFoundError, CredentialService
from backend.app.modules.deployments.models import (
    Deployment,
    DeploymentExecution,
    DeploymentRevision,
    DeploymentTarget,
    DeploymentTargetExecution,
)
from backend.app.modules.integrations.models import Integration, IntegrationState
from backend.app.modules.inventory.models import Server
from backend.app.modules.jobs.models import CustomOperationalAction
from backend.app.modules.packages.models import PackageDefinitionRecord
from backend.app.modules.profiles.models import InfrastructureProfileRecord
from backend.app.modules.provisioning.models import ProvisioningBatch, ProvisioningBlueprint, ProvisioningRequest
from backend.app.modules.trash.schemas import TrashGroupRead, TrashItemRead, TrashListRead, TrashReferenceRead, TrashUsageRead


class TrashItemNotFoundError(Exception):
    """Raised when a trashed item cannot be found."""


class TrashItemInUseError(Exception):
    """Raised when an item still has references that block permanent deletion."""


class TrashOperationUnsupportedError(Exception):
    """Raised when a trash action is not supported for an item type."""


class TrashService:
    GROUP_TITLES = {
        "credential": "Credentials",
        "package": "Packages",
        "profile": "Profiles",
        "deployment": "Deployments",
        "automation": "Automations",
        "integration": "Integrations",
        "provisioning_blueprint": "Provisioning Blueprints",
        "provisioning_request": "Provisioning Requests",
        "operational_action": "Operational Actions",
        "inventory_server": "Inventory",
    }

    MODEL_BY_TYPE = {
        "package": PackageDefinitionRecord,
        "profile": InfrastructureProfileRecord,
        "deployment": Deployment,
        "automation": Automation,
        "integration": Integration,
        "provisioning_blueprint": ProvisioningBlueprint,
        "provisioning_request": ProvisioningRequest,
        "operational_action": CustomOperationalAction,
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.credential_service = CredentialService(repository=CredentialRepository(session))

    async def list_trash(self) -> TrashListRead:
        groups: dict[str, list[TrashItemRead]] = {item_type: [] for item_type in self.GROUP_TITLES}

        for credential in await self._scalars(select(Credential).where(Credential.deleted_at.is_not(None))):
            references = await self.credential_service.find_references(credential)
            groups["credential"].append(
                self._item(
                    "credential",
                    credential.id,
                    credential.name,
                    credential.deleted_at,
                    credential.deleted_by,
                    credential.delete_reason,
                    reference_count=len(references),
                    metadata={"credential_type": str(credential.credential_type), "scope": str(credential.scope)},
                )
            )

        for item_type, model in self.MODEL_BY_TYPE.items():
            rows = await self._scalars(select(model).where(model.deleted_at.is_not(None)).order_by(model.deleted_at.desc()))
            for row in rows:
                references = await self.references(item_type, row.id)
                groups[item_type].append(
                    self._item(
                        item_type,
                        row.id,
                        self._name_for(row),
                        row.deleted_at,
                        row.deleted_by,
                        row.delete_reason,
                        reference_count=len(references.references),
                        metadata=self._metadata_for(item_type, row),
                    )
                )

        inactive_states = {
            InventoryLifecycleState.ARCHIVED,
            InventoryLifecycleState.DECOMMISSIONED,
            InventoryLifecycleState.DELETED,
        }
        servers = await self._scalars(
            select(Server)
            .where(Server.lifecycle_state.in_(inactive_states))
            .order_by(Server.updated_at.desc())
        )
        for server in servers:
            references = await self.references("inventory_server", server.id)
            groups["inventory_server"].append(
                self._item(
                    "inventory_server",
                    server.id,
                    server.hostname,
                    server.updated_at,
                    None,
                    None,
                    purge_supported=False,
                    reference_count=len(references.references),
                    metadata={
                        "ip_address": server.ip_address,
                        "lifecycle_state": server.lifecycle_state.value,
                        "node_type": server.node_type.value,
                    },
                )
            )

        return TrashListRead(
            groups=[
                TrashGroupRead(item_type=item_type, title=title, items=groups[item_type])
                for item_type, title in self.GROUP_TITLES.items()
                if groups[item_type]
            ]
        )

    async def references(self, item_type: str, item_id: UUID) -> TrashUsageRead:
        if item_type == "credential":
            credential = await self.credential_service.repository.get_by_id(item_id, include_deleted=True)
            if credential is None:
                raise TrashItemNotFoundError("Trash item not found")
            references = [
                TrashReferenceRead(**reference.model_dump())
                for reference in await self.credential_service.find_references(credential)
            ]
            return TrashUsageRead(item_type=item_type, item_id=str(item_id), references=references)

        item = await self._get(item_type, item_id, include_deleted=True)
        if item is None and item_type != "inventory_server":
            raise TrashItemNotFoundError("Trash item not found")

        references: list[TrashReferenceRead] = []
        reference_key = self._reference_key(item_type, item)

        if item_type == "package":
            references.extend(await self._profile_step_references(reference_key, "package", "package_id"))
            references.extend(await self._automation_references(reference_key, AutomationOperationType.PACKAGE))
            references.extend(await self._provisioning_bootstrap_references(reference_key, "bootstrap_package_ids"))
        elif item_type == "profile":
            references.extend(await self._automation_references(reference_key, AutomationOperationType.PROFILE))
            references.extend(await self._provisioning_bootstrap_references(reference_key, "bootstrap_profile_ids"))
        elif item_type == "deployment":
            references.extend(await self._profile_step_references(reference_key, "deployment", "deployment_id"))
            references.extend(await self._automation_references(reference_key, AutomationOperationType.DEPLOYMENT))
        elif item_type == "operational_action":
            references.extend(await self._profile_step_references(reference_key, "action", "action_id"))
            references.extend(await self._automation_references(reference_key, AutomationOperationType.ACTION))
        elif item_type == "provisioning_blueprint":
            batches = await self._scalars(select(ProvisioningBatch).where(ProvisioningBatch.blueprint_id == item_id))
            references.extend(
                TrashReferenceRead(
                    reference_type="provisioning_batch",
                    reference_id=str(batch.id),
                    name=batch.name,
                    field="blueprint_id",
                    detail="Provisioning batch created from this blueprint",
                )
                for batch in batches
            )
        elif item_type == "integration":
            servers = await self._scalars(select(Server).where(Server.integration_id == item_id))
            references.extend(
                TrashReferenceRead(
                    reference_type="inventory_server",
                    reference_id=str(server.id),
                    name=server.hostname,
                    field="integration_id",
                    detail="Inventory record discovered through this integration",
                )
                for server in servers
            )
        elif item_type == "inventory_server":
            references.extend(await self._server_references(item_id))

        return TrashUsageRead(item_type=item_type, item_id=str(item_id), references=references)

    async def restore(self, item_type: str, item_id: UUID) -> TrashItemRead:
        if item_type == "credential":
            try:
                credential = await self.credential_service.restore_credential(item_id)
            except CredentialNotFoundError as exc:
                raise TrashItemNotFoundError("Trash item not found") from exc
            return TrashItemRead(
                item_type="credential",
                item_id=str(credential.id),
                name=credential.name,
                reference_count=credential.reference_count,
                metadata={"credential_type": str(credential.credential_type), "scope": str(credential.scope)},
            )

        if item_type == "inventory_server":
            server = await self._get_inventory_server(item_id)
            server.lifecycle_state = InventoryLifecycleState.MANAGED
            server.managed = True
            await self.session.commit()
            await self.session.refresh(server)
            return self._item("inventory_server", server.id, server.hostname, None, None, None, purge_supported=False)

        item = await self._get(item_type, item_id, include_deleted=True)
        if item is None:
            raise TrashItemNotFoundError("Trash item not found")
        item.deleted_at = None
        item.deleted_by = None
        item.delete_reason = None
        if isinstance(item, Automation):
            item.enabled = False
        if isinstance(item, Integration):
            item.state = IntegrationState.DISCONNECTED if item.enabled else IntegrationState.DISABLED
        await self.session.commit()
        await self.session.refresh(item)
        return self._item(item_type, item.id, self._name_for(item), None, None, None, metadata=self._metadata_for(item_type, item))

    async def purge(self, item_type: str, item_id: UUID) -> None:
        if item_type == "credential":
            try:
                await self.credential_service.purge_credential(item_id)
                return
            except CredentialNotFoundError as exc:
                raise TrashItemNotFoundError("Trash item not found") from exc
            except CredentialInUseError as exc:
                raise TrashItemInUseError(str(exc)) from exc

        if item_type == "inventory_server":
            raise TrashOperationUnsupportedError("Inventory records use archive/decommission lifecycle and cannot be purged from universal Trash yet.")

        item = await self._get(item_type, item_id, include_deleted=True)
        if item is None or item.deleted_at is None:
            raise TrashItemNotFoundError("Trash item not found")

        references = await self.references(item_type, item_id)
        if references.references:
            raise TrashItemInUseError(
                f"{self.GROUP_TITLES.get(item_type, 'Item')} item is still referenced by "
                f"{len(references.references)} record(s). Clear or change those references before permanent deletion."
            )

        if item_type == "deployment":
            await self._purge_deployment(item_id)
        else:
            await self.session.delete(item)
        await self.session.commit()

    async def _profile_step_references(self, reference_key: str, step_type: str, field: str) -> list[TrashReferenceRead]:
        references: list[TrashReferenceRead] = []
        profiles = await self._scalars(select(InfrastructureProfileRecord).where(InfrastructureProfileRecord.deleted_at.is_(None)))
        for profile in profiles:
            for index, step in enumerate(profile.steps or [], start=1):
                kind = str(step.get("type") or step.get("kind") or "")
                target = str(step.get("reference_id") or step.get(field) or step.get("id") or "")
                if kind == step_type and target == reference_key:
                    references.append(
                        TrashReferenceRead(
                            reference_type="profile",
                            reference_id=str(profile.id),
                            name=profile.name,
                            field=f"steps[{index}]",
                            detail=f"Profile step references {step_type}",
                        )
                    )
        return references

    async def _automation_references(self, reference_key: str, operation_type: AutomationOperationType) -> list[TrashReferenceRead]:
        automations = await self._scalars(
            select(Automation).where(
                Automation.deleted_at.is_(None),
                Automation.operation_type == operation_type,
                Automation.reference_id == reference_key,
            )
        )
        return [
            TrashReferenceRead(
                reference_type="automation",
                reference_id=str(automation.id),
                name=automation.name,
                field="reference_id",
                detail=f"Automation runs {operation_type.value}",
            )
            for automation in automations
        ]

    async def _provisioning_bootstrap_references(self, reference_key: str, field: str) -> list[TrashReferenceRead]:
        references: list[TrashReferenceRead] = []
        requests = await self._scalars(select(ProvisioningRequest).where(ProvisioningRequest.deleted_at.is_(None)))
        for request in requests:
            if reference_key in {str(item) for item in getattr(request, field, []) or []}:
                references.append(
                    TrashReferenceRead(
                        reference_type="provisioning_request",
                        reference_id=str(request.id),
                        name=request.vm_name,
                        field=field,
                        detail="Provisioning bootstrap reference",
                    )
                )
        blueprints = await self._scalars(select(ProvisioningBlueprint).where(ProvisioningBlueprint.deleted_at.is_(None)))
        for blueprint in blueprints:
            if reference_key in {str(item) for item in getattr(blueprint, field, []) or []}:
                references.append(
                    TrashReferenceRead(
                        reference_type="provisioning_blueprint",
                        reference_id=str(blueprint.id),
                        name=blueprint.name,
                        field=field,
                        detail="Blueprint bootstrap reference",
                    )
                )
        return references

    async def _server_references(self, server_id: UUID) -> list[TrashReferenceRead]:
        references: list[TrashReferenceRead] = []
        deployments = await self._scalars(select(DeploymentTarget).where(DeploymentTarget.server_id == server_id))
        references.extend(
            TrashReferenceRead(
                reference_type="deployment_target",
                reference_id=str(target.id),
                name=str(target.deployment_id),
                field="server_id",
                detail="Deployment target points at this server",
            )
            for target in deployments
        )
        automations = await self._scalars(select(Automation).where(Automation.deleted_at.is_(None)))
        references.extend(
            TrashReferenceRead(
                reference_type="automation",
                reference_id=str(automation.id),
                name=automation.name,
                field="target_server_ids",
                detail="Automation targets this server",
            )
            for automation in automations
            if str(server_id) in {str(item) for item in automation.target_server_ids}
        )
        return references

    async def _purge_deployment(self, deployment_id: UUID) -> None:
        await self.session.execute(
            DeploymentTargetExecution.__table__.delete().where(DeploymentTargetExecution.deployment_id == deployment_id)
        )
        await self.session.execute(DeploymentExecution.__table__.delete().where(DeploymentExecution.deployment_id == deployment_id))
        await self.session.execute(DeploymentRevision.__table__.delete().where(DeploymentRevision.deployment_id == deployment_id))
        await self.session.execute(DeploymentTarget.__table__.delete().where(DeploymentTarget.deployment_id == deployment_id))
        deployment = await self._get("deployment", deployment_id, include_deleted=True)
        if deployment is not None:
            await self.session.delete(deployment)

    async def _get(self, item_type: str, item_id: UUID, *, include_deleted: bool = False) -> Any | None:
        if item_type == "inventory_server":
            return await self._get_inventory_server(item_id)
        model = self.MODEL_BY_TYPE.get(item_type)
        if model is None:
            raise TrashOperationUnsupportedError(f"Trash item type {item_type} is not supported.")
        query = select(model).where(model.id == item_id)
        if not include_deleted:
            query = query.where(model.deleted_at.is_(None))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _get_inventory_server(self, server_id: UUID) -> Server:
        result = await self.session.execute(select(Server).where(Server.id == server_id))
        server = result.scalar_one_or_none()
        if server is None:
            raise TrashItemNotFoundError("Trash item not found")
        return server

    async def _scalars(self, query: Any) -> list[Any]:
        result = await self.session.execute(query)
        return list(result.scalars().all())

    def _reference_key(self, item_type: str, item: Any) -> str:
        if item_type in {"package", "profile", "operational_action"}:
            return str(item.slug)
        return str(item.id)

    def _name_for(self, item: Any) -> str:
        return str(getattr(item, "name", None) or getattr(item, "slug", None) or getattr(item, "vm_name", None) or item.id)

    def _metadata_for(self, item_type: str, item: Any) -> dict[str, object]:
        if item_type in {"package", "profile", "operational_action"}:
            return {"slug": item.slug, "category": getattr(item, "category", None)}
        if item_type == "automation":
            return {"operation_type": item.operation_type.value, "enabled": item.enabled}
        if item_type == "deployment":
            return {"status": item.status.value}
        if item_type == "integration":
            return {"provider_type": item.provider_type.value, "enabled": item.enabled}
        if item_type == "provisioning_request":
            return {"status": item.status.value, "target_node": item.target_node}
        if item_type == "provisioning_blueprint":
            return {"target_node": item.target_node, "environment": item.environment}
        return {}

    def _item(
        self,
        item_type: str,
        item_id: UUID,
        name: str,
        deleted_at: datetime | None,
        deleted_by: str | None,
        delete_reason: str | None,
        *,
        restore_supported: bool = True,
        purge_supported: bool = True,
        reference_count: int = 0,
        metadata: dict[str, object] | None = None,
    ) -> TrashItemRead:
        return TrashItemRead(
            item_type=item_type,
            item_id=str(item_id),
            name=name,
            deleted_at=deleted_at,
            deleted_by=deleted_by,
            delete_reason=delete_reason,
            restore_supported=restore_supported,
            purge_supported=purge_supported,
            reference_count=reference_count,
            metadata=metadata or {},
        )

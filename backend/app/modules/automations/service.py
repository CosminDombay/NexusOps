from datetime import UTC, datetime
from uuid import UUID

from backend.app.modules.automations.models import Automation, AutomationOperationType
from backend.app.modules.automations.repository import AutomationRepository
from backend.app.modules.automations.schemas import AutomationCreate, AutomationRead, AutomationTargetRead, AutomationUpdate
from backend.app.modules.inventory.models import InventoryLifecycleState
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.schemas import JobActionExecuteRequest
from backend.app.modules.jobs.service import JobService, OperationalActionNotFoundError
from backend.app.modules.orchestration.security import CommandValidationError
from backend.app.modules.orchestration.semantics import workflow_failure_states, workflow_runtime_state
from backend.app.modules.packages.schemas import PackageExecuteRequest
from backend.app.modules.packages.service import PackageAutomationService, PackageDefinitionNotFoundError
from backend.app.modules.profiles.schemas import ProfileApplyRequest
from backend.app.modules.profiles.service import ProfileNotFoundError, ProfileService, ProfileStepResolutionError
from backend.app.modules.workflows.models import WorkflowStatus, WorkflowTriggerSource, WorkflowType
from backend.app.modules.workflows.schemas import WorkflowCreate, WorkflowStepCreate
from backend.app.modules.workflows.service import WorkflowService


class AutomationNotFoundError(Exception):
    """Raised when an automation cannot be found."""


class AutomationValidationError(Exception):
    """Raised when automation configuration is invalid."""


class AutomationExecutionError(Exception):
    """Raised when an automation run fails in a known orchestration domain."""


AUTOMATION_EXECUTION_ERRORS = (
    AutomationValidationError,
    CommandValidationError,
    OperationalActionNotFoundError,
    PackageDefinitionNotFoundError,
    ProfileNotFoundError,
    ProfileStepResolutionError,
)


class AutomationService:
    def __init__(
        self,
        *,
        repository: AutomationRepository,
        server_repository: ServerRepository,
        workflow_service: WorkflowService,
        job_service: JobService | None = None,
        profile_service: ProfileService | None = None,
        package_service: PackageAutomationService | None = None,
    ) -> None:
        self.repository = repository
        self.server_repository = server_repository
        self.workflow_service = workflow_service
        self.job_service = job_service
        self.profile_service = profile_service
        self.package_service = package_service

    async def list_automations(self, *, target_server_id: UUID | None = None) -> list[AutomationRead]:
        automations = (
            await self.repository.list_for_target(target_server_id)
            if target_server_id is not None
            else await self.repository.list()
        )
        workflows = await self.workflow_service.list_workflows(target_server_id=target_server_id)
        servers = await self.server_repository.list(include_inactive=True)
        return [
            self._to_read(
                automation,
                workflows=[workflow for workflow in workflows if workflow.context_json.get("automation_id") == str(automation.id)],
                servers=servers,
            )
            for automation in automations
        ]

    async def create_automation(self, payload: AutomationCreate) -> AutomationRead:
        self._validate_supported_operation(payload.operation_type)
        await self._validate_targets([str(item) for item in payload.target_server_ids])
        automation = await self.repository.create(
            Automation(
                name=payload.name,
                description=payload.description,
                enabled=payload.enabled,
                schedule_type=payload.schedule_type,
                cron_expression=payload.cron_expression,
                interval_seconds=payload.interval_seconds,
                target_mode=payload.target_mode,
                target_server_ids=[str(item) for item in payload.target_server_ids],
                operation_type=payload.operation_type,
                reference_id=payload.reference_id,
                raw_command=payload.raw_command,
                variables_json=payload.variables_json,
                credential_refs=payload.credential_refs,
                execution_credential_ref=payload.execution_credential_ref,
            )
        )
        await self.repository.session.commit()
        return self._to_read(automation)

    async def update_automation(self, automation_id: UUID, payload: AutomationUpdate) -> AutomationRead:
        automation = await self._automation(automation_id)
        update_data = payload.model_dump(exclude_unset=True)
        if "operation_type" in update_data and update_data["operation_type"] is not None:
            self._validate_supported_operation(update_data["operation_type"])
        if "target_server_ids" in update_data and update_data["target_server_ids"] is not None:
            update_data["target_server_ids"] = [str(item) for item in update_data["target_server_ids"]]
            await self._validate_targets(update_data["target_server_ids"])
        for key, value in update_data.items():
            setattr(automation, key, value)
        await self.repository.session.commit()
        await self.repository.session.refresh(automation)
        return self._to_read(automation)

    async def delete_automation(self, automation_id: UUID) -> None:
        automation = await self._automation(automation_id)
        automation.deleted_at = datetime.now(UTC)
        automation.enabled = False
        await self.repository.session.commit()

    async def enable_automation(self, automation_id: UUID) -> AutomationRead:
        automation = await self._automation(automation_id)
        automation.enabled = True
        await self.repository.session.commit()
        await self.repository.session.refresh(automation)
        return self._to_read(automation)

    async def disable_automation(self, automation_id: UUID) -> AutomationRead:
        automation = await self._automation(automation_id)
        automation.enabled = False
        await self.repository.session.commit()
        await self.repository.session.refresh(automation)
        return self._to_read(automation)

    async def create_run_workflow(
        self,
        automation_id: UUID,
        *,
        trigger_source: WorkflowTriggerSource = WorkflowTriggerSource.MANUAL,
    ):
        automation = await self._automation(automation_id)
        target_server_id = UUID(automation.target_server_ids[0]) if automation.target_server_ids else None
        workflow_type = {
            AutomationOperationType.ACTION: WorkflowType.SCHEDULED_ACTION,
            AutomationOperationType.PROFILE: WorkflowType.SCHEDULED_PROFILE,
            AutomationOperationType.PACKAGE: WorkflowType.SCHEDULED_PACKAGE,
        }.get(automation.operation_type)
        if workflow_type is None:
            raise AutomationValidationError("Only action, profile, and package automations are supported initially")

        workflow = await self.workflow_service.create_workflow(
            WorkflowCreate(
                workflow_type=workflow_type,
                trigger_source=trigger_source,
                target_server_id=target_server_id,
                context_json={"automation_id": str(automation.id), "automation_name": automation.name},
            )
        )
        await self.workflow_service.mark_queued(workflow.id)
        return workflow

    async def execute_automation_workflow(self, automation_id: UUID, workflow_run_id: UUID) -> None:
        automation = await self._automation(automation_id)
        await self.workflow_service.start_workflow(workflow_run_id)
        status = WorkflowStatus.SUCCESS
        result_summary: dict[str, object] = {"automation_id": str(automation.id), "jobs": []}

        try:
            for index, server_id in enumerate(automation.target_server_ids, start=1):
                step = await self.workflow_service.add_step(
                    workflow_run_id,
                    WorkflowStepCreate(
                        step_order=index,
                        step_type=automation.operation_type.value,
                        name=f"{automation.name} on {server_id}",
                        metadata_json={"target_server_id": server_id},
                    ),
                )
                await self.workflow_service.start_step(step.id)
                try:
                    jobs = await self._execute_operation(automation, UUID(server_id))
                    result_summary["jobs"] = [*result_summary["jobs"], *[str(job.id) for job in jobs]]
                    await self.workflow_service.complete_step(
                        step.id,
                        log_output="\n".join((job.stdout or "").strip() for job in jobs if job.stdout),
                        metadata_json={"job_ids": [str(job.id) for job in jobs]},
                    )
                except AUTOMATION_EXECUTION_ERRORS as exc:
                    status = WorkflowStatus.FAILED
                    await self.workflow_service.fail_step(step.id, str(exc))
                    raise
            await self.workflow_service.complete_workflow(workflow_run_id, result_summary=result_summary)
        except AUTOMATION_EXECUTION_ERRORS as exc:
            await self.workflow_service.fail_workflow(workflow_run_id, str(exc), result_summary=result_summary)
        finally:
            automation.last_run_at = datetime.now(UTC)
            automation.last_status = status.value
            await self.repository.session.commit()

    async def _execute_operation(self, automation: Automation, target_server_id: UUID):
        if automation.operation_type == AutomationOperationType.ACTION:
            if self.job_service is None:
                raise AutomationValidationError("Job service is required for action automations")
            job = await self.job_service.execute_action(
                JobActionExecuteRequest(
                    target_server_id=target_server_id,
                    action_id=automation.reference_id or "",
                    credential_ref=automation.execution_credential_ref,
                )
            )
            return [job]

        if automation.operation_type == AutomationOperationType.PACKAGE:
            if self.package_service is None:
                raise AutomationValidationError("Package service is required for package automations")
            job = await self.package_service.execute_definition(
                automation.reference_id or "",
                PackageExecuteRequest(
                    target_server_id=target_server_id,
                    variables=automation.variables_json,
                    credential_refs=automation.credential_refs,
                    execution_credential_ref=automation.execution_credential_ref,
                ),
            )
            return [job]

        if automation.operation_type == AutomationOperationType.PROFILE:
            if self.profile_service is None:
                raise AutomationValidationError("Profile service is required for profile automations")
            result = await self.profile_service.apply_profile(
                automation.reference_id or "",
                ProfileApplyRequest(
                    target_server_id=target_server_id,
                    variables=automation.variables_json,
                    credential_refs=automation.credential_refs,
                    execution_credential_ref=automation.execution_credential_ref,
                ),
            )
            return result.jobs

        raise AutomationValidationError("Only action, profile, and package automations are supported initially")

    async def _validate_targets(self, server_ids: list[str]) -> None:
        for server_id in server_ids:
            server = await self.server_repository.get_by_id(UUID(server_id))
            if server is None:
                raise AutomationValidationError(f"Target server not found: {server_id}")
            if not server.managed or server.lifecycle_state == InventoryLifecycleState.ARCHIVED:
                raise AutomationValidationError(f"Target server is not executable: {server.hostname}")

    async def _automation(self, automation_id: UUID) -> Automation:
        automation = await self.repository.get_by_id(automation_id)
        if automation is None:
            raise AutomationNotFoundError("Automation not found")
        return automation

    @staticmethod
    def _validate_supported_operation(operation_type: AutomationOperationType) -> None:
        if operation_type not in {
            AutomationOperationType.ACTION,
            AutomationOperationType.PROFILE,
            AutomationOperationType.PACKAGE,
        }:
            raise AutomationValidationError("Only action, profile, and package automations are supported initially")

    def _to_read(self, automation: Automation, *, workflows=None, servers=None) -> AutomationRead:
        workflows = sorted(workflows or [], key=lambda item: item.created_at, reverse=True)
        servers = servers or []
        target_nodes = []
        for server_id in automation.target_server_ids:
            server = next((item for item in servers if str(item.id) == str(server_id)), None)
            if server:
                target_nodes.append(
                    AutomationTargetRead(
                        id=str(server.id),
                        hostname=server.hostname,
                        node_type=server.node_type.value,
                        environment=server.environment.value,
                        provider=server.provider,
                        source=server.source,
                        tags=server.tags,
                    )
                )
        last_success = next((workflow for workflow in workflows if workflow.status == WorkflowStatus.SUCCESS), None)
        last_failure = next((workflow for workflow in workflows if workflow.status in workflow_failure_states()), None)
        recent = workflows[:5]
        last = recent[0] if recent else None
        runtime_state = "disabled" if not automation.enabled else "idle"
        if automation.enabled and last:
            runtime_state = workflow_runtime_state(last.status)

        return AutomationRead.model_validate(automation).model_copy(
            update={
                "runtime_state": runtime_state,
                "last_success_at": last_success.finished_at if last_success else None,
                "last_failure_at": last_failure.finished_at if last_failure else None,
                "last_duration_seconds": last.duration_seconds if last else None,
                "execution_count": len(workflows),
                "target_nodes": target_nodes,
                "recent_executions": recent,
            }
        )

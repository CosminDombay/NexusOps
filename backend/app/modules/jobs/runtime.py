from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.app.adapters.ssh import SshAdapter
from backend.app.adapters.ssh.sudo import prepare_sudo_command
from backend.app.modules.audit.service import AuditService
from backend.app.modules.credentials.service import CredentialNotFoundError, CredentialService
from backend.app.modules.inventory.models import ServerSshAuthMethod
from backend.app.modules.jobs.models import Job, JobStatus
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.schemas import JobExecuteRequest
from backend.app.modules.orchestration.semantics import (
    JOB_LIFECYCLE,
    is_job_success,
    orchestration_origin,
    runtime_metadata,
)
from backend.app.modules.orchestration.security import SecretSanitizer, SSHExecutionError
from backend.app.modules.orchestration.utils import duration_seconds


TERMINAL_JOB_STATES = JOB_LIFECYCLE.terminal

VALID_JOB_TRANSITIONS = {
    JobStatus.PENDING: {JobStatus.QUEUED, JobStatus.CANCELLED, JobStatus.STALE},
    JobStatus.QUEUED: {JobStatus.DISPATCHED, JobStatus.CANCELLED, JobStatus.STALE},
    JobStatus.DISPATCHED: {JobStatus.RUNNING, JobStatus.CANCELLED, JobStatus.STALE},
    JobStatus.RUNNING: {JobStatus.SUCCESS, JobStatus.FAILED, JobStatus.COMPLETED, JobStatus.CANCELLED, JobStatus.STALE},
    JobStatus.COMPLETED: set(),
    JobStatus.SUCCESS: set(),
    JobStatus.FAILED: set(),
    JobStatus.CANCELLED: set(),
    JobStatus.STALE: set(),
}


class InvalidJobStateTransitionError(Exception):
    """Raised when a job state transition violates the execution state machine."""


@dataclass(frozen=True)
class ExecutionCancellationIntent:
    job_id: UUID
    requested_at: datetime
    reason: str = "cancel_requested"


class ExecutionCancellationRegistry:
    """In-process cancellation intent registry for currently owned runtime work."""

    def __init__(self) -> None:
        self._intents: dict[UUID, ExecutionCancellationIntent] = {}

    def request(self, job_id: UUID, *, reason: str = "cancel_requested") -> ExecutionCancellationIntent:
        intent = ExecutionCancellationIntent(job_id=job_id, requested_at=datetime.now(UTC), reason=reason)
        self._intents[job_id] = intent
        return intent

    def get(self, job_id: UUID) -> ExecutionCancellationIntent | None:
        return self._intents.get(job_id)

    def clear(self, job_id: UUID) -> None:
        self._intents.pop(job_id, None)


class JobExecutionRuntime:
    """Coordinates job execution lifecycle, runtime metadata, and transport calls."""

    def __init__(
        self,
        *,
        job_repository: JobRepository,
        ssh_adapter: SshAdapter,
        credential_service: CredentialService | None = None,
        audit_service: AuditService | None = None,
        cancellation_registry: ExecutionCancellationRegistry | None = None,
    ) -> None:
        self.job_repository = job_repository
        self.ssh_adapter = ssh_adapter
        self.credential_service = credential_service
        self.audit_service = audit_service
        self.cancellation_registry = cancellation_registry or execution_cancellations
        self.secret_sanitizer = SecretSanitizer()

    async def run(self, *, job: Job, server, payload: JobExecuteRequest) -> Job:
        correlation_id = job.correlation_id or str(uuid4())
        job.correlation_id = correlation_id
        job.execution_origin = job.execution_origin or orchestration_origin(payload.operation_type)
        job.runtime_metadata = {
            **(job.runtime_metadata or {}),
            **runtime_metadata(
                operation_type=payload.operation_type,
                execution_origin=job.execution_origin,
                correlation_id=correlation_id,
                target_hostname=server.hostname,
                target_server_id=str(server.id),
                transport=self.ssh_adapter.name,
            ),
        }
        await self.transition(job, JobStatus.QUEUED)
        await self.transition(job, JobStatus.DISPATCHED)
        if await self._cancelled(job):
            return job
        await self.transition(job, JobStatus.RUNNING)

        started = job.started_at or datetime.now(UTC)
        try:
            ssh_user, ssh_password, ssh_private_key_path, ssh_private_key, ssh_passphrase = await self._credentials(server, payload)
            command, input_data = prepare_sudo_command(payload.command, ssh_password)
            result = await self.ssh_adapter.run_command(
                host=server.ip_address,
                port=server.ssh_port,
                command=command,
                user=ssh_user,
                password=ssh_password,
                private_key_path=ssh_private_key_path,
                private_key=ssh_private_key,
                passphrase=ssh_passphrase,
                input_data=input_data,
            )
            job.stdout = self.secret_sanitizer.redact_text(result.stdout)
            job.stderr = self.secret_sanitizer.redact_text(result.stderr)
            job.exit_code = result.exit_code
            job.output_events = self._output_events(job, stdout=job.stdout or "", stderr=job.stderr or "")
            next_status = JobStatus.SUCCESS if result.exit_code == 0 else JobStatus.FAILED
            if await self._cancelled(job, transition=False):
                next_status = JobStatus.CANCELLED
            await self.transition(job, next_status, started_at=started)
        except Exception as exc:
            safe_error = self.secret_sanitizer.redact_text(str(exc)) or "SSH execution failed"
            if await self._cancelled(job, transition=False):
                job.stderr = safe_error or "Job cancelled during execution"
                await self.transition(job, JobStatus.CANCELLED, started_at=started)
            else:
                job.stdout = ""
                job.stderr = safe_error
                job.exit_code = None
                job.output_events = self._output_events(job, stderr=safe_error)
                await self.transition(job, JobStatus.FAILED, started_at=started)

        await self._audit(job, server)
        self.cancellation_registry.clear(job.id)
        return job

    async def transition(self, job: Job, next_status: JobStatus, *, started_at: datetime | None = None) -> None:
        current = job.status
        if current == next_status:
            return
        if next_status not in VALID_JOB_TRANSITIONS[current]:
            raise InvalidJobStateTransitionError(f"Cannot transition job from {current.value} to {next_status.value}")
        now = datetime.now(UTC)
        job.status = next_status
        if next_status == JobStatus.QUEUED:
            job.queued_at = job.queued_at or now
        elif next_status == JobStatus.DISPATCHED:
            job.dispatched_at = job.dispatched_at or now
        elif next_status == JobStatus.RUNNING:
            job.started_at = job.started_at or now
        elif next_status in TERMINAL_JOB_STATES:
            job.completed_at = job.completed_at or now
            start = started_at or job.started_at or job.queued_at
            job.runtime_duration_seconds = duration_seconds(
                start,
                job.completed_at,
                default_to_now=False,
            )
        job.runtime_metadata = {
            **(job.runtime_metadata or {}),
            "last_transition_at": now.isoformat(),
            "terminal": next_status in TERMINAL_JOB_STATES,
        }
        await self.job_repository.session.commit()
        await self.job_repository.session.refresh(job)

    async def request_cancel(self, job: Job, *, reason: str = "cancel_requested") -> Job:
        intent = self.cancellation_registry.request(job.id, reason=reason)
        job.cancellation_requested_at = intent.requested_at
        job.runtime_metadata = {
            **(job.runtime_metadata or {}),
            "cancellation_intent": reason,
            "cancellation_requested_at": intent.requested_at.isoformat(),
        }
        if job.status in {JobStatus.PENDING, JobStatus.QUEUED, JobStatus.DISPATCHED, JobStatus.RUNNING}:
            await self.transition(job, JobStatus.CANCELLED)
        else:
            await self.job_repository.session.commit()
            await self.job_repository.session.refresh(job)
        return job

    async def _cancelled(self, job: Job, *, transition: bool = True) -> bool:
        if self.cancellation_registry.get(job.id) is None and job.cancellation_requested_at is None:
            return False
        if transition and job.status not in TERMINAL_JOB_STATES:
            await self.transition(job, JobStatus.CANCELLED)
        return True

    async def _credentials(self, server, payload: JobExecuteRequest):
        ssh_user = server.ssh_username
        ssh_password = server.ssh_password if server.ssh_auth_method == ServerSshAuthMethod.PASSWORD else None
        ssh_private_key_path = server.ssh_private_key_path if server.ssh_auth_method == ServerSshAuthMethod.KEY else None
        ssh_private_key: str | None = None
        ssh_passphrase: str | None = None
        self.secret_sanitizer.add_secret(ssh_password)
        credential_ref = payload.credential_ref or (str(server.credential_id) if server.credential_id is not None else None)
        if credential_ref:
            if self.credential_service is None:
                raise CredentialNotFoundError("Credential service is required for credential-backed execution")
            credential = await self.credential_service.resolve_credential(credential_ref)
            ssh_user = credential.username or ssh_user
            if credential.credential_type in {"password", "ssh_password"}:
                ssh_password = credential.secret
                self.secret_sanitizer.add_secret(ssh_password)
                ssh_private_key_path = None
            elif credential.credential_type == "ssh_key":
                ssh_password = None
                ssh_private_key_path = None
                ssh_private_key = credential.private_key
                ssh_passphrase = credential.passphrase
                self.secret_sanitizer.add_secret(ssh_private_key)
                self.secret_sanitizer.add_secret(ssh_passphrase)
        return ssh_user, ssh_password, ssh_private_key_path, ssh_private_key, ssh_passphrase

    async def _audit(self, job: Job, server) -> None:
        if self.audit_service is None:
            return
        await self.audit_service.record(
            event_type=self._audit_event_type(job.operation_type),
            target_type="server",
            target_id=server.id,
            result="success" if is_job_success(job.status) else "failed",
            metadata={
                "job_id": str(job.id),
                "operation_type": job.operation_type,
                "exit_code": job.exit_code,
                "target_hostname": server.hostname,
                "correlation_id": job.correlation_id,
                "runtime_duration_seconds": job.runtime_duration_seconds,
            },
            error=job.stderr if not is_job_success(job.status) else None,
        )

    @staticmethod
    def _output_events(job: Job, *, stdout: str = "", stderr: str = "") -> list[dict[str, object]]:
        now = datetime.now(UTC).isoformat()
        events = list(job.output_events or [])
        if stdout:
            events.append({"stream": "stdout", "content": stdout, "created_at": now, "sequence": len(events) + 1})
        if stderr:
            events.append({"stream": "stderr", "content": stderr, "created_at": now, "sequence": len(events) + 1})
        return events

    @staticmethod
    def _audit_event_type(operation_type: str) -> str:
        prefix = operation_type.split(":", 1)[0]
        return {
            "action": "job.action_executed",
            "package": "package.executed",
            "profile": "profile.executed",
            "deployment": "deployment.action_executed",
            "provisioning": "provisioning.action_executed",
            "identity": "identity.action_executed",
        }.get(prefix, "job.executed")


execution_cancellations = ExecutionCancellationRegistry()

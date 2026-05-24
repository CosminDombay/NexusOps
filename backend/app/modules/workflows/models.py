from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, TimestampMixin, UuidPrimaryKeyMixin


class WorkflowStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowTriggerSource(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    PROVISIONING = "provisioning"
    SYSTEM = "system"


class WorkflowType(StrEnum):
    PROVISION_VM = "provision_vm"
    PROFILE_EXECUTION = "profile_execution"
    PACKAGE_EXECUTION = "package_execution"
    DEPLOYMENT_EXECUTION = "deployment_execution"
    SCHEDULED_ACTION = "scheduled_action"
    SCHEDULED_PROFILE = "scheduled_profile"
    SCHEDULED_PACKAGE = "scheduled_package"


class WorkflowStepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowRun(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workflow_runs"

    workflow_type: Mapped[WorkflowType] = mapped_column(
        Enum(WorkflowType, name="workflow_type", values_callable=lambda enum: [member.value for member in enum]),
        nullable=False,
        index=True,
    )
    status: Mapped[WorkflowStatus] = mapped_column(
        Enum(WorkflowStatus, name="workflow_status", values_callable=lambda enum: [member.value for member in enum]),
        default=WorkflowStatus.PENDING,
        nullable=False,
        index=True,
    )
    trigger_source: Mapped[WorkflowTriggerSource] = mapped_column(
        Enum(
            WorkflowTriggerSource,
            name="workflow_trigger_source",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=WorkflowTriggerSource.MANUAL,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    target_server_id: Mapped[UUID | None] = mapped_column(ForeignKey("servers.id"), nullable=True, index=True)
    initiated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # TODO: formalize context keys per workflow_type before adding workflow chaining.
    context_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    # TODO: promote stable summary counters and correlation fields to typed columns.
    result_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    steps: Mapped[list["WorkflowStep"]] = relationship(
        back_populates="workflow_run",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="WorkflowStep.step_order",
    )


class WorkflowStep(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "workflow_steps"

    workflow_run_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_runs.id"), nullable=False, index=True)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[WorkflowStepStatus] = mapped_column(
        Enum(
            WorkflowStepStatus,
            name="workflow_step_status",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=WorkflowStepStatus.PENDING,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    log_output: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error_output: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # TODO: split target/job linkage metadata into typed columns for queryable runtime visibility.
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    workflow_run: Mapped[WorkflowRun] = relationship(back_populates="steps")

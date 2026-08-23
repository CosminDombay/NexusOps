from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class ExecutionSummary:
    """Normalized execution counters for orchestration reads and rollups."""

    total_count: int
    success_count: int
    failed_count: int
    job_ids: list[str] = field(default_factory=list)
    failure_messages: list[str] = field(default_factory=list)

    @property
    def failure_count(self) -> int:
        return self.failed_count

    @property
    def has_failures(self) -> bool:
        return self.failed_count > 0

    @property
    def all_successful(self) -> bool:
        return self.total_count > 0 and self.success_count == self.total_count

    def as_result_summary(self) -> dict[str, Any]:
        return {
            "target_count": self.total_count,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "job_ids": self.job_ids,
        }


@dataclass(frozen=True)
class TargetExecutionAggregate:
    """Aggregated view of per-target execution outcomes."""

    summary: ExecutionSummary
    statuses: list[Any]


def duration_seconds(
    started_at: datetime | None,
    finished_at: datetime | None,
    *,
    default_to_now: bool = True,
) -> int | None:
    if started_at is None:
        return None
    if finished_at is None and not default_to_now:
        return None
    start = ensure_aware_utc(started_at)
    end = ensure_aware_utc(finished_at or datetime.now(UTC))
    return max(0, int((end - start).total_seconds()))


def summarize_statuses(
    items: Iterable[Any],
    *,
    success_states: set[Any],
    failure_states: set[Any],
) -> ExecutionSummary:
    values = list(items)
    return ExecutionSummary(
        total_count=len(values),
        success_count=sum(1 for item in values if status_value(item) in success_states),
        failed_count=sum(1 for item in values if status_value(item) in failure_states),
    )


def aggregate_target_executions(
    target_executions: Iterable[Any],
    *,
    success_states: set[Any],
    failure_states: set[Any],
) -> TargetExecutionAggregate:
    executions = list(target_executions)
    status_summary = summarize_statuses(
        executions,
        success_states=success_states,
        failure_states=failure_states,
    )
    summary = ExecutionSummary(
        total_count=status_summary.total_count,
        success_count=status_summary.success_count,
        failed_count=status_summary.failed_count,
        job_ids=[str(job_id) for item in executions if (job_id := getattr(item, "job_id", None))],
        failure_messages=[
            message
            for item in executions
            if (message := getattr(item, "error_message", None))
        ],
    )
    return TargetExecutionAggregate(
        summary=summary,
        statuses=[status_value(item) for item in executions],
    )


def rollup_status(
    statuses: Iterable[Any],
    *,
    success_states: set[Any],
    failure_states: set[Any],
    empty_status: Any,
    all_success_status: Any,
    partial_success_status: Any,
    all_failed_status: Any,
    mixed_status: Any,
) -> Any:
    values = list(statuses)
    if not values:
        return empty_status
    summary = summarize_statuses(
        values,
        success_states=success_states,
        failure_states=failure_states,
    )
    if summary.success_count == len(values):
        return all_success_status
    if summary.success_count and summary.failed_count:
        return partial_success_status
    if summary.failed_count == len(values):
        return all_failed_status
    return mixed_status


def success_failure_counts(
    items: Iterable[Any],
    *,
    success_attr: str = "success",
) -> tuple[int, int]:
    values = list(items)
    success_count = sum(1 for item in values if bool(getattr(item, success_attr)))
    return success_count, len(values) - success_count


def status_value(item: Any) -> Any:
    return getattr(item, "status", item)


def ensure_aware_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)

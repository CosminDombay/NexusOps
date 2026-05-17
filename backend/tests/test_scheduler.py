from backend.app.modules.automations.models import Automation, AutomationOperationType, AutomationScheduleType, AutomationTargetMode
from backend.app.workers.scheduler.service import SchedulerService


def test_scheduler_builds_interval_trigger() -> None:
    automation = Automation(
        name="Uptime",
        enabled=True,
        schedule_type=AutomationScheduleType.INTERVAL,
        interval_seconds=300,
        target_mode=AutomationTargetMode.SINGLE_HOST,
        target_server_ids=[],
        operation_type=AutomationOperationType.ACTION,
        reference_id="uptime",
    )

    trigger = SchedulerService._trigger_for(automation)

    assert trigger is not None


def test_scheduler_builds_cron_trigger() -> None:
    automation = Automation(
        name="Nightly",
        enabled=True,
        schedule_type=AutomationScheduleType.CRON,
        cron_expression="0 2 * * *",
        target_mode=AutomationTargetMode.MULTIPLE_HOSTS,
        target_server_ids=[],
        operation_type=AutomationOperationType.ACTION,
        reference_id="docker-status",
    )

    trigger = SchedulerService._trigger_for(automation)

    assert trigger is not None

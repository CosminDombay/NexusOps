from datetime import UTC, datetime
from uuid import UUID

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.config import settings
from backend.app.db.session import AsyncSessionLocal
from backend.app.modules.automations.models import Automation, AutomationScheduleType
from backend.app.modules.automations.repository import AutomationRepository
from backend.app.modules.automations.tasks import execute_automation_workflow
from backend.app.modules.monitoring.tasks import validate_monitoring_snapshots
from backend.app.modules.workflows.models import WorkflowTriggerSource
from backend.app.workers.queue.service import task_queue

logger = structlog.get_logger(__name__)


class SchedulerService:
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler()

    async def start(self) -> None:
        await self.reload_automations()
        self.register_monitoring_validation()
        self.scheduler.start()
        logger.info("scheduler_started")

    async def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        await task_queue.cancel_all()
        logger.info("scheduler_stopped")

    async def reload_automations(self) -> None:
        self.scheduler.remove_all_jobs()
        self.register_monitoring_validation()
        try:
            async with AsyncSessionLocal() as session:
                automations = await AutomationRepository(session).list_enabled()
        except SQLAlchemyError as exc:
            logger.warning("scheduler_automation_load_skipped", reason=str(exc))
            automations = []
        for automation in automations:
            self.register_automation(automation)

    def register_automation(self, automation: Automation) -> None:
        trigger = self._trigger_for(automation)
        if trigger is None:
            return
        self.scheduler.add_job(
            self.dispatch_automation,
            trigger=trigger,
            args=[automation.id],
            id=f"automation:{automation.id}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )
        job = self.scheduler.get_job(f"automation:{automation.id}")
        automation.next_run_at = self._job_next_run_time(job, trigger)

    def register_monitoring_validation(self) -> None:
        self.scheduler.add_job(
            self.dispatch_monitoring_validation,
            trigger=IntervalTrigger(seconds=settings.monitoring_validation_interval_seconds),
            id="monitoring:validation",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
        )

    async def dispatch_monitoring_validation(self) -> None:
        task_queue.submit(validate_monitoring_snapshots())

    async def dispatch_automation(self, automation_id: UUID) -> None:
        from backend.app.modules.automations.factory import build_automation_service

        async with AsyncSessionLocal() as session:
            service = build_automation_service(session)
            workflow = await service.create_run_workflow(
                automation_id,
                trigger_source=WorkflowTriggerSource.SCHEDULED,
            )
        task_queue.submit(execute_automation_workflow(automation_id, workflow.id))

    @staticmethod
    def _trigger_for(automation: Automation):
        if automation.schedule_type == AutomationScheduleType.INTERVAL and automation.interval_seconds:
            return IntervalTrigger(seconds=automation.interval_seconds)
        if automation.schedule_type == AutomationScheduleType.CRON and automation.cron_expression:
            minute, hour, day, month, day_of_week = automation.cron_expression.split()
            return CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
            )
        return None

    @staticmethod
    def _job_next_run_time(job, trigger):
        if job is not None:
            try:
                return job.next_run_time
            except AttributeError:
                pass
        return trigger.get_next_fire_time(None, datetime.now(UTC))


scheduler_service = SchedulerService()

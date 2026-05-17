from uuid import UUID

from backend.app.db.session import AsyncSessionLocal
from backend.app.modules.automations.factory import build_automation_service


async def execute_automation_workflow(automation_id: UUID, workflow_run_id: UUID) -> None:
    async with AsyncSessionLocal() as session:
        service = build_automation_service(session)
        await service.execute_automation_workflow(automation_id, workflow_run_id)

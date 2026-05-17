from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.ssh import ParamikoSshAdapter
from backend.app.modules.automations.repository import AutomationRepository
from backend.app.modules.automations.service import AutomationService
from backend.app.modules.credentials.repository import CredentialRepository
from backend.app.modules.credentials.service import CredentialService
from backend.app.modules.deployments.repository import DeploymentRepository, DeploymentRevisionRepository, DeploymentTargetRepository
from backend.app.modules.deployments.service import DockerComposeDeploymentService
from backend.app.modules.inventory.repository import ServerRepository
from backend.app.modules.jobs.repository import JobRepository
from backend.app.modules.jobs.service import JobService
from backend.app.modules.packages.repository import PackageDefinitionRepository
from backend.app.modules.packages.service import PackageAutomationService
from backend.app.modules.profiles.repository import InfrastructureProfileRepository
from backend.app.modules.profiles.service import ProfileService
from backend.app.modules.workflows.repository import WorkflowRunRepository, WorkflowStepRepository
from backend.app.modules.workflows.service import WorkflowService


def build_automation_service(session: AsyncSession) -> AutomationService:
    credential_service = CredentialService(repository=CredentialRepository(session))
    server_repository = ServerRepository(session)
    job_service = JobService(
        job_repository=JobRepository(session),
        server_repository=server_repository,
        ssh_adapter=ParamikoSshAdapter(),
        credential_service=credential_service,
    )
    workflow_service = WorkflowService(
        workflow_repository=WorkflowRunRepository(session),
        step_repository=WorkflowStepRepository(session),
    )
    package_repository = PackageDefinitionRepository(session)
    deployment_service = DockerComposeDeploymentService(
        repository=DeploymentRepository(session),
        target_repository=DeploymentTargetRepository(session),
        revision_repository=DeploymentRevisionRepository(session),
        server_repository=server_repository,
        job_service=job_service,
        credential_service=credential_service,
    )
    profile_service = ProfileService(
        job_service=job_service,
        repository=InfrastructureProfileRepository(session),
        package_repository=package_repository,
        deployment_service=deployment_service,
    )
    package_service = PackageAutomationService(
        repository=package_repository,
        job_service=job_service,
        credential_service=credential_service,
    )
    return AutomationService(
        repository=AutomationRepository(session),
        server_repository=server_repository,
        workflow_service=workflow_service,
        job_service=job_service,
        profile_service=profile_service,
        package_service=package_service,
    )

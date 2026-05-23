from fastapi import APIRouter, Depends

from backend.app.api.v1.routes import health
from backend.app.modules.auth.api.router import router as auth_router
from backend.app.modules.auth.security.dependencies import require_admin, require_operator, require_viewer
from backend.app.modules.audit.router import router as audit_router
from backend.app.modules.automations.router import router as automations_router
from backend.app.modules.credentials.router import router as credentials_router
from backend.app.modules.deployments.router import router as deployments_router
from backend.app.modules.inventory.router import router as inventory_router
from backend.app.modules.integrations.router import router as integrations_router
from backend.app.modules.identity.router import router as identity_router
from backend.app.modules.jobs.router import router as jobs_router
from backend.app.modules.monitoring.router import router as monitoring_router
from backend.app.modules.packages.router import router as packages_router
from backend.app.modules.proxmox.router import router as proxmox_router
from backend.app.modules.profiles.router import router as profiles_router
from backend.app.modules.provisioning.router import router as provisioning_router
from backend.app.modules.remote_access.router import router as remote_access_router
from backend.app.modules.runtime_state.router import router as runtime_state_router
from backend.app.modules.variables.router import router as variables_router
from backend.app.modules.workflows.router import router as workflows_router

api_v1_router = APIRouter()
api_v1_router.include_router(health.router, tags=["health"])
api_v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(
    audit_router,
    prefix="/audit-events",
    tags=["audit-events"],
    dependencies=[Depends(require_admin)],
)
api_v1_router.include_router(
    automations_router,
    prefix="/automations",
    tags=["automations"],
    dependencies=[Depends(require_operator)],
)
api_v1_router.include_router(
    credentials_router,
    prefix="/credentials",
    tags=["credentials"],
    dependencies=[Depends(require_admin)],
)
api_v1_router.include_router(
    provisioning_router,
    prefix="/vms",
    tags=["vms"],
    dependencies=[Depends(require_operator)],
)
api_v1_router.include_router(
    inventory_router,
    prefix="/servers",
    tags=["servers"],
    dependencies=[Depends(require_viewer)],
)
api_v1_router.include_router(
    identity_router,
    prefix="/identity",
    tags=["identity"],
    dependencies=[Depends(require_admin)],
)
api_v1_router.include_router(
    deployments_router,
    prefix="/deployments",
    tags=["deployments"],
    dependencies=[Depends(require_operator)],
)
api_v1_router.include_router(
    integrations_router,
    prefix="/integrations",
    tags=["integrations"],
    dependencies=[Depends(require_admin)],
)
api_v1_router.include_router(
    packages_router,
    prefix="/packages",
    tags=["packages"],
    dependencies=[Depends(require_operator)],
)
api_v1_router.include_router(
    monitoring_router,
    prefix="/monitoring",
    tags=["monitoring"],
    dependencies=[Depends(require_viewer)],
)
api_v1_router.include_router(
    profiles_router,
    prefix="/profiles",
    tags=["profiles"],
    dependencies=[Depends(require_operator)],
)
api_v1_router.include_router(
    jobs_router,
    prefix="/jobs",
    tags=["jobs"],
    dependencies=[Depends(require_operator)],
)
api_v1_router.include_router(
    proxmox_router,
    prefix="/proxmox",
    tags=["proxmox"],
    dependencies=[Depends(require_viewer)],
)
api_v1_router.include_router(
    remote_access_router,
    prefix="/remote-access",
    tags=["remote-access"],
)
api_v1_router.include_router(
    runtime_state_router,
    prefix="/runtime-state",
    tags=["runtime-state"],
    dependencies=[Depends(require_viewer)],
)
api_v1_router.include_router(
    variables_router,
    prefix="/variables",
    tags=["variables"],
    dependencies=[Depends(require_admin)],
)
api_v1_router.include_router(
    workflows_router,
    prefix="/workflows",
    tags=["workflows"],
    dependencies=[Depends(require_viewer)],
)

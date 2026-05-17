from fastapi import APIRouter

from backend.app.api.v1.routes import health
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
from backend.app.modules.variables.router import router as variables_router
from backend.app.modules.workflows.router import router as workflows_router

api_v1_router = APIRouter()
api_v1_router.include_router(health.router, tags=["health"])
api_v1_router.include_router(automations_router, prefix="/automations", tags=["automations"])
api_v1_router.include_router(credentials_router, prefix="/credentials", tags=["credentials"])
api_v1_router.include_router(provisioning_router, prefix="/vms", tags=["vms"])
api_v1_router.include_router(inventory_router, prefix="/servers", tags=["servers"])
api_v1_router.include_router(identity_router, prefix="/identity", tags=["identity"])
api_v1_router.include_router(deployments_router, prefix="/deployments", tags=["deployments"])
api_v1_router.include_router(integrations_router, prefix="/integrations", tags=["integrations"])
api_v1_router.include_router(packages_router, prefix="/packages", tags=["packages"])
api_v1_router.include_router(monitoring_router, prefix="/monitoring", tags=["monitoring"])
api_v1_router.include_router(profiles_router, prefix="/profiles", tags=["profiles"])
api_v1_router.include_router(jobs_router, prefix="/jobs", tags=["jobs"])
api_v1_router.include_router(proxmox_router, prefix="/proxmox", tags=["proxmox"])
api_v1_router.include_router(variables_router, prefix="/variables", tags=["variables"])
api_v1_router.include_router(workflows_router, prefix="/workflows", tags=["workflows"])

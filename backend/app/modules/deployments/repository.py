from backend.app.common.repository import BaseRepository
from backend.app.modules.deployments.models import Deployment


class DeploymentRepository(BaseRepository[Deployment]):
    pass


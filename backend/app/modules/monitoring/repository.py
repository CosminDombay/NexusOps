from backend.app.common.repository import BaseRepository
from backend.app.modules.monitoring.models import MetricSample


class MetricSampleRepository(BaseRepository[MetricSample]):
    pass


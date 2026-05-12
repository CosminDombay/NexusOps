from backend.app.common.repository import BaseRepository
from backend.app.modules.jobs.models import Job, JobLog


class JobRepository(BaseRepository[Job]):
    pass


class JobLogRepository(BaseRepository[JobLog]):
    pass


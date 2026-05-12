from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, UuidPrimaryKeyMixin


class MetricSample(Base, UuidPrimaryKeyMixin):
    __tablename__ = "metric_samples"

    server_id: Mapped[UUID] = mapped_column(ForeignKey("servers.id"), index=True)
    metric_name: Mapped[str] = mapped_column(String(100), index=True)
    value: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(32))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


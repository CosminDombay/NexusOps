from datetime import datetime

from pydantic import BaseModel, Field


class TrashReferenceRead(BaseModel):
    reference_type: str
    reference_id: str
    name: str
    field: str
    detail: str | None = None


class TrashItemRead(BaseModel):
    item_type: str
    item_id: str
    name: str
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    delete_reason: str | None = None
    restore_supported: bool = True
    purge_supported: bool = True
    reference_count: int = 0
    metadata: dict[str, object] = Field(default_factory=dict)


class TrashGroupRead(BaseModel):
    item_type: str
    title: str
    items: list[TrashItemRead] = Field(default_factory=list)


class TrashListRead(BaseModel):
    groups: list[TrashGroupRead] = Field(default_factory=list)


class TrashUsageRead(BaseModel):
    item_type: str
    item_id: str
    references: list[TrashReferenceRead] = Field(default_factory=list)

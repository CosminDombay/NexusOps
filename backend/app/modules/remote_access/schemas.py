from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RemoteFileType(StrEnum):
    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    OTHER = "other"


class RemoteFileEntry(BaseModel):
    name: str
    path: str
    type: RemoteFileType
    size: int
    modified_at: datetime | None = None
    permissions: str
    owner: str | None = None
    group: str | None = None


class RemoteDirectoryListing(BaseModel):
    path: str
    entries: list[RemoteFileEntry]


class RemoteFileRead(BaseModel):
    path: str
    content: str
    sha256: str
    size: int
    modified_at: datetime | None = None


class RemoteFileWriteRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    content: str
    expected_hash: str = Field(min_length=64, max_length=71)


class RemoteFileWriteResponse(BaseModel):
    path: str
    sha256: str
    size: int
    modified_at: datetime | None = None

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class SequenceOut(BaseModel):
    id: UUID
    filename: str
    format: str
    status: str
    checksum_sha256: str
    base_count: int | None = None
    read_count: int | None = None
    gc_content: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MetadataUpdate(BaseModel):
    metadata: dict[str, Any] | None = None
    tags: list[str] | None = None

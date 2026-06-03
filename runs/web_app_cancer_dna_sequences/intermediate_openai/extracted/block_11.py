import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.models.user import Base

sequence_tags = Table(
    "sequence_tags",
    Base.metadata,
    Column("sequence_id", UUID(as_uuid=True), ForeignKey("sequences.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), unique=True, index=True, nullable=False)


class Sequence(Base):
    __tablename__ = "sequences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    filename = Column(String(255), nullable=False)
    format = Column(String(10), nullable=False)  # fasta or fastq
    content_type = Column(String(120), nullable=True)
    storage_path = Column(Text, nullable=False)
    checksum_sha256 = Column(String(64), nullable=False, index=True)

    status = Column(String(40), default="uploaded", index=True, nullable=False)
    error = Column(Text, nullable=True)

    base_count = Column(Integer, nullable=True)
    read_count = Column(Integer, nullable=True)
    gc_content = Column(String(20), nullable=True)

    index_path = Column(Text, nullable=True)

    metadata_json = Column("metadata", JSONB, default=dict, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner = relationship("User", back_populates="sequences")
    tags = relationship("Tag", secondary=sequence_tags, lazy="joined")

    __table_args__ = (
        UniqueConstraint("owner_id", "checksum_sha256", name="uq_owner_sequence_checksum"),
    )

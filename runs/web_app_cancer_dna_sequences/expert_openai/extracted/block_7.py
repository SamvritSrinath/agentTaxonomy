import uuid
from sqlalchemy import (
    Column,
    String,
    Integer,
    BigInteger,
    ForeignKey,
    DateTime,
    Text,
    Float,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def uuid_str():
    return str(uuid.uuid4())


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=uuid_str)
    name = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(String, primary_key=True, default=uuid_str)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    version = Column(Integer, nullable=False)
    parent_dataset_id = Column(String, ForeignKey("datasets.id"), nullable=True)
    status = Column(String, nullable=False, default="CREATED")
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    files = relationship("GenomicFile", cascade="all,delete")


class GenomicFile(Base):
    __tablename__ = "files"

    id = Column(String, primary_key=True, default=uuid_str)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False, index=True)
    object_key = Column(Text, nullable=False)
    filename = Column(String, nullable=False)
    kind = Column(String, nullable=False)
    checksum_sha256 = Column(String, nullable=True)
    size_bytes = Column(BigInteger, nullable=False)
    status = Column(String, nullable=False, default="PENDING_UPLOAD")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class GenomicIndex(Base):
    __tablename__ = "indexes"

    id = Column(String, primary_key=True, default=uuid_str)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False, index=True)
    file_id = Column(String, ForeignKey("files.id"), nullable=False, index=True)
    index_type = Column(String, nullable=False)
    object_key = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Search(Base):
    __tablename__ = "searches"

    id = Column(String, primary_key=True, default=uuid_str)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    dataset_id = Column(String, ForeignKey("datasets.id"), nullable=False)
    query = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="QUEUED")
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)


class SearchHit(Base):
    __tablename__ = "search_hits"

    id = Column(String, primary_key=True, default=uuid_str)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False, index=True)
    search_id = Column(String, ForeignKey("searches.id"), nullable=False, index=True)
    file_id = Column(String, ForeignKey("files.id"), nullable=False)
    contig = Column(String, nullable=True)
    line_number = Column(Integer, nullable=True)
    snippet = Column(Text, nullable=False)
    score = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

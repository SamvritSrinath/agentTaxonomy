from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum

class UploadStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    uploads = relationship("Upload", back_populates="user")

class Upload(Base):
    __tablename__ = "uploads"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # fasta or fastq
    storage_path = Column(String, nullable=False)
    status = Column(Enum(UploadStatus), default=UploadStatus.PENDING)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    user = relationship("User", back_populates="uploads")
    sequences = relationship("Sequence", back_populates="upload")

class Sequence(Base):
    __tablename__ = "sequences"
    id = Column(Integer, primary_key=True, index=True)
    upload_id = Column(Integer, ForeignKey("uploads.id"), nullable=False)
    sequence_id = Column(String, nullable=False)   # e.g., "chr1" or sequence header
    description = Column(Text, nullable=True)
    sequence = Column(Text, nullable=False)
    length = Column(Integer, nullable=False)
    quality = Column(Text, nullable=True)          # only for FASTQ
    md5 = Column(String, index=True)               # MD5 of sequence for fast lookup
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    upload = relationship("Upload", back_populates="sequences")

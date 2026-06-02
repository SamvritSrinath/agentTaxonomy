Below is a runnable modular FastAPI/PostgreSQL scaffold for a cancer genomics sequence-management platform with JWT login, FASTA/FASTQ upload validation, metadata/tags, and background sequence indexing.

---

## Project layout

```text
cancer-genomics-platform/
  docker-compose.yml
  Dockerfile
  requirements.txt
  .env.example
  backend/
    app/
      __init__.py
      main.py
      core/
        __init__.py
        config.py
        security.py
      db/
        __init__.py
        base.py
        session.py
      models/
        __init__.py
        user.py
        sequence.py
      schemas/
        __init__.py
        auth.py
        sequence.py
      api/
        __init__.py
        deps.py
        routes/
          __init__.py
          auth.py
          sequences.py
      services/
        __init__.py
        validators.py
        storage.py
        indexing.py
  frontend/
    index.html
  tests/
    test_validators.py
    test_security.py
```

---

## `requirements.txt`

```txt
fastapi==0.115.6
uvicorn[standard]==0.34.0
SQLAlchemy==2.0.36
psycopg2-binary==2.9.10
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.20
pydantic-settings==2.7.0
email-validator==2.2.0
pytest==8.3.4
httpx==0.28.1
```

---

## `.env.example`

```env
DATABASE_URL=postgresql+psycopg2://genomics:genomics@localhost:5432/genomics
SECRET_KEY=change-this-to-a-long-random-secret
ACCESS_TOKEN_EXPIRE_MINUTES=60
UPLOAD_DIR=./data/uploads
MAX_UPLOAD_MB=200
ALLOWED_ORIGINS=["http://localhost:8000","http://localhost:5173"]
```

---

## `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend

ENV PYTHONPATH=/app/backend

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## `docker-compose.yml`

```yaml
services:
  db:
    image: postgres:16
    container_name: genomics-postgres
    environment:
      POSTGRES_USER: genomics
      POSTGRES_PASSWORD: genomics
      POSTGRES_DB: genomics
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  api:
    build: .
    container_name: genomics-api
    depends_on:
      - db
    environment:
      DATABASE_URL: postgresql+psycopg2://genomics:genomics@db:5432/genomics
      SECRET_KEY: change-this-to-a-long-random-secret
      ACCESS_TOKEN_EXPIRE_MINUTES: 60
      UPLOAD_DIR: /data/uploads
      MAX_UPLOAD_MB: 200
      ALLOWED_ORIGINS: '["http://localhost:8000","http://localhost:5173"]'
    ports:
      - "8000:8000"
    volumes:
      - uploads:/data/uploads

volumes:
  pgdata:
  uploads:
```

---

# Backend source code

## `backend/app/core/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Cancer Genomics Platform"
    DATABASE_URL: str = "postgresql+psycopg2://genomics:genomics@localhost:5432/genomics"
    SECRET_KEY: str = "dev-only-change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    UPLOAD_DIR: str = "./data/uploads"
    MAX_UPLOAD_MB: int = 200
    ALLOWED_ORIGINS: list[str] = ["http://localhost:8000", "http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
```

---

## `backend/app/core/security.py`

```python
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

ALGORITHM = "HS256"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)


def create_access_token(subject: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expires}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
```

---

## `backend/app/db/session.py`

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)
```

---

## `backend/app/db/base.py`

```python
from app.models.user import Base as Base  # noqa: F401
from app.models.sequence import Sequence, Tag  # noqa: F401
```

---

## `backend/app/models/user.py`

```python
from sqlalchemy import Boolean, Column, DateTime, Integer, String, func
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(320), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sequences = relationship(
        "Sequence",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
```

---

## `backend/app/models/sequence.py`

```python
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
```

---

## `backend/app/schemas/auth.py`

```python
from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    is_active: bool

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

---

## `backend/app/schemas/sequence.py`

```python
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
```

---

## `backend/app/api/deps.py`

```python
from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import ALGORITHM
from app.db.session import SessionLocal
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        subject = payload.get("sub")
        if subject is None:
            raise credentials_error
        user_id = int(subject)
    except (JWTError, ValueError):
        raise credentials_error

    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).first()
    if user is None:
        raise credentials_error

    return user
```

---

## `backend/app/services/validators.py`

```python
import re
from typing import BinaryIO, Literal

VALID_NT_RE = re.compile(r"^[ACGTUNRYSWKMBDHV\-.]+$", re.IGNORECASE)


class SequenceValidationError(ValueError):
    pass


def _iter_lines(file_obj: BinaryIO):
    file_obj.seek(0)
    for raw in file_obj:
        if isinstance(raw, bytes):
            try:
                line = raw.decode("ascii")
            except UnicodeDecodeError as exc:
                raise SequenceValidationError("Sequence file must be ASCII text") from exc
        else:
            line = raw
        yield line.rstrip("\r\n")


def _first_nonempty_line(file_obj: BinaryIO) -> str | None:
    for line in _iter_lines(file_obj):
        if line.strip():
            return line.strip()
    return None


def _validate_fasta(file_obj: BinaryIO) -> dict:
    records = 0
    bases = 0
    gc = 0
    seen_header = False
    record_has_sequence = False

    for line in _iter_lines(file_obj):
        line = line.strip()
        if not line:
            continue

        if line.startswith(">"):
            if seen_header and not record_has_sequence:
                raise SequenceValidationError("FASTA record has no sequence")
            seen_header = True
            record_has_sequence = False
            records += 1
            continue

        if not seen_header:
            raise SequenceValidationError("FASTA must start with a header line beginning with '>'")

        seq = line.upper()
        if not VALID_NT_RE.match(seq):
            raise SequenceValidationError("FASTA contains invalid nucleotide symbols")

        record_has_sequence = True
        bases += len(seq)
        gc += seq.count("G") + seq.count("C")

    if not seen_header:
        raise SequenceValidationError("Empty FASTA file")
    if not record_has_sequence:
        raise SequenceValidationError("Last FASTA record has no sequence")

    gc_content = f"{(gc / bases * 100):.2f}%" if bases else "0.00%"
    return {
        "format": "fasta",
        "read_count": records,
        "base_count": bases,
        "gc_content": gc_content,
    }


def _next_nonempty(iterator):
    for line in iterator:
        if line.strip():
            return line.strip()
    return None


def _validate_fastq(file_obj: BinaryIO) -> dict:
    iterator = _iter_lines(file_obj)
    records = 0
    bases = 0
    gc = 0

    while True:
        header = _next_nonempty(iterator)
        if header is None:
            break

        try:
            seq = next(iterator).strip()
            plus = next(iterator).strip()
            qual = next(iterator).rstrip("\r\n")
        except StopIteration as exc:
            raise SequenceValidationError("Incomplete FASTQ record") from exc

        if not header.startswith("@"):
            raise SequenceValidationError("FASTQ header must start with '@'")
        if not plus.startswith("+"):
            raise SequenceValidationError("FASTQ separator must start with '+'")
        if not seq:
            raise SequenceValidationError("FASTQ sequence cannot be empty")
        if not VALID_NT_RE.match(seq):
            raise SequenceValidationError("FASTQ contains invalid nucleotide symbols")
        if len(seq) != len(qual):
            raise SequenceValidationError("FASTQ quality length must match sequence length")
        if any(ord(ch) < 33 or ord(ch) > 126 for ch in qual):
            raise SequenceValidationError("FASTQ quality scores must be printable ASCII")

        seq = seq.upper()
        records += 1
        bases += len(seq)
        gc += seq.count("G") + seq.count("C")

    if records == 0:
        raise SequenceValidationError("Empty FASTQ file")

    gc_content = f"{(gc / bases * 100):.2f}%" if bases else "0.00%"
    return {
        "format": "fastq",
        "read_count": records,
        "base_count": bases,
        "gc_content": gc_content,
    }


def validate_upload(
    file_obj: BinaryIO,
    declared_format: Literal["fasta", "fastq"] | str | None = None,
) -> dict:
    first = _first_nonempty_line(file_obj)
    if first is None:
        raise SequenceValidationError("Empty sequence file")

    detected = "fasta" if first.startswith(">") else "fastq" if first.startswith("@") else None
    if detected is None:
        raise SequenceValidationError("Could not detect FASTA or FASTQ format")

    if declared_format:
        declared = declared_format.lower()
        if declared not in {"fasta", "fastq"}:
            raise SequenceValidationError("Declared format must be fasta or fastq")
        if declared != detected:
            raise SequenceValidationError(f"Declared format {declared} does not match detected {detected}")

    file_obj.seek(0)
    if detected == "fasta":
        result = _validate_fasta(file_obj)
    else:
        result = _validate_fastq(file_obj)

    file_obj.seek(0)
    return result
```

---

## `backend/app/services/storage.py`

```python
import hashlib
import os
import re
import uuid
from typing import BinaryIO

from app.core.config import settings


def _safe_filename(filename: str) -> str:
    base = os.path.basename(filename or "sequence.dat").replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9_.-]", "_", base)[:180]


def save_upload_file(file_obj: BinaryIO, original_filename: str) -> tuple[str, str, int]:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    filename = f"{uuid.uuid4()}_{_safe_filename(original_filename)}"
    destination = os.path.join(settings.UPLOAD_DIR, filename)

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    total = 0
    sha256 = hashlib.sha256()

    try:
        with open(destination, "wb") as out:
            while True:
                chunk = file_obj.read(1024 * 1024)
                if not chunk:
                    break

                total += len(chunk)
                if total > max_bytes:
                    raise ValueError(f"Upload exceeds maximum size of {settings.MAX_UPLOAD_MB} MB")

                sha256.update(chunk)
                out.write(chunk)
    except Exception:
        if os.path.exists(destination):
            os.remove(destination)
        raise

    return destination, sha256.hexdigest(), total
```

---

## `backend/app/services/indexing.py`

```python
import json
from collections import Counter
from pathlib import Path
from uuid import UUID

from app.db.session import SessionLocal
from app.models.sequence import Sequence


def _iter_fasta_sequences(path: str):
    buf: list[str] = []
    with open(path, "rt", encoding="ascii") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if buf:
                    yield "".join(buf).upper()
                    buf = []
            else:
                buf.append(line)
        if buf:
            yield "".join(buf).upper()


def _iter_fastq_sequences(path: str):
    with open(path, "rt", encoding="ascii") as handle:
        while True:
            header = handle.readline()
            if not header:
                break
            seq = handle.readline().strip()
            handle.readline()
            handle.readline()
            if seq:
                yield seq.upper()


def index_sequence(sequence_id: UUID, k: int = 11) -> None:
    db = SessionLocal()
    try:
        seq = db.query(Sequence).filter(Sequence.id == sequence_id).first()
        if seq is None:
            return

        seq.status = "indexing"
        seq.error = None
        db.commit()

        iterator = (
            _iter_fasta_sequences(seq.storage_path)
            if seq.format == "fasta"
            else _iter_fastq_sequences(seq.storage_path)
        )

        counts: Counter[str] = Counter()
        for sequence in iterator:
            if len(sequence) < k:
                continue
            for i in range(0, len(sequence) - k + 1):
                kmer = sequence[i : i + k]
                counts[kmer]

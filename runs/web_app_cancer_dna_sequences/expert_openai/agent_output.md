Below is a deployment-ready reference implementation scaffold for a scalable cancer genomics data platform. It includes FastAPI microservices, Kafka events, PostgreSQL metadata/versioning, S3-compatible object storage, Kubernetes/Helm infrastructure, monitoring, and OPA/Gatekeeper policies.

---

## 1. Architecture

```text
Researchers
   |
   v
API Gateway
   |
   +--> Upload Service
   |       - Validates JWT tenant/role
   |       - Creates versioned datasets
   |       - Issues presigned S3/MinIO URLs
   |       - Emits Kafka ingestion events
   |
   +--> Search Service
   |       - Creates distributed sequence search jobs
   |       - Publishes Kafka jobs
   |       - Reads search results from PostgreSQL
   |
Kafka
   |
   +--> Indexer Workers
   |       - Consume ingestion events
   |       - Build FASTA/FASTQ/BAM/VCF indexes
   |       - Upload indexes to object storage
   |       - Update dataset versions/status
   |
   +--> Search Workers
           - Consume distributed search jobs
           - Search object shards
           - Write hits to PostgreSQL

PostgreSQL
   - Tenants
   - Users
   - Versioned datasets
   - Files
   - Index metadata
   - Search jobs/results

Object Storage
   - Raw FASTA/FASTQ/BAM/VCF
   - Index artifacts
   - Search artifacts

Kubernetes
   - API gateway
   - Upload service
   - Search service
   - Indexer workers
   - Search workers
   - PostgreSQL
   - Kafka
   - MinIO/S3
   - Prometheus/Grafana/OTel

Policy
   - JWT RBAC
   - Tenant isolation
   - Kubernetes OPA/Gatekeeper
   - Non-root containers
   - Restricted networking
```

---

## 2. Repository layout

```text
genomics-platform/
  Makefile
  pyproject.toml
  migrations/
    001_init.sql
  libs/
    genomics_common/
      __init__.py
      auth.py
      config.py
      db.py
      events.py
      models.py
      observability.py
      storage.py
      genomics.py
  services/
    Dockerfile
    api-gateway/
      app.py
    upload-service/
      app.py
    indexer-worker/
      app.py
    search-service/
      app.py
    search-worker/
      app.py
  tests/
    test_auth.py
    test_genomics.py
    test_upload_security.py
  infra/
    helm/
      genomics-platform/
        Chart.yaml
        values.yaml
        templates/
          configmap.yaml
          secret.yaml
          deployments.yaml
          services.yaml
          ingress.yaml
          networkpolicy.yaml
          servicemonitor.yaml
          hpa.yaml
    opa/
      gatekeeper-security.yaml
      tenant-access.rego
    monitoring/
      otel-collector.yaml
      grafana-dashboard.json
```

---

# 3. Source code

## `pyproject.toml`

```toml
[project]
name = "genomics-platform"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi==0.115.6",
  "uvicorn[standard]==0.34.0",
  "sqlalchemy==2.0.36",
  "psycopg2-binary==2.9.10",
  "pydantic==2.10.4",
  "boto3==1.35.90",
  "confluent-kafka==2.6.1",
  "PyJWT==2.10.1",
  "httpx==0.28.1",
  "prometheus-client==0.21.1",
  "opentelemetry-api==1.29.0",
  "opentelemetry-sdk==1.29.0",
  "opentelemetry-instrumentation-fastapi==0.50b0",
  "python-multipart==0.0.20"
]

[project.optional-dependencies]
test = [
  "pytest==8.3.4",
  "pytest-cov==6.0.0"
]

[tool.pytest.ini_options]
pythonpath = ["libs"]
testpaths = ["tests"]
```

---

## `Makefile`

```makefile
REGISTRY ?= ghcr.io/example
VERSION ?= 0.1.0

SERVICES = api-gateway upload-service indexer-worker search-service search-worker

install:
	pip install -e ".[test]"

test:
	pytest -q --cov=libs --cov=services

build:
	for s in $(SERVICES); do \
	  docker build -f services/Dockerfile \
	    --build-arg SERVICE=$$s \
	    -t $(REGISTRY)/genomics-$$s:$(VERSION) . ; \
	done

push:
	for s in $(SERVICES); do \
	  docker push $(REGISTRY)/genomics-$$s:$(VERSION) ; \
	done

deploy:
	helm dependency update infra/helm/genomics-platform
	helm upgrade --install genomics-platform infra/helm/genomics-platform \
	  --namespace genomics --create-namespace \
	  --set global.imageRegistry=$(REGISTRY) \
	  --set global.imageTag=$(VERSION)

lint-policy:
	opa test infra/opa || true
```

---

## `migrations/001_init.sql`

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS tenants (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS datasets (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  name TEXT NOT NULL,
  version INTEGER NOT NULL,
  parent_dataset_id UUID NULL REFERENCES datasets(id),
  status TEXT NOT NULL DEFAULT 'CREATED',
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name, version)
);

CREATE TABLE IF NOT EXISTS files (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  object_key TEXT NOT NULL,
  filename TEXT NOT NULL,
  kind TEXT NOT NULL,
  checksum_sha256 TEXT NULL,
  size_bytes BIGINT NOT NULL,
  status TEXT NOT NULL DEFAULT 'PENDING_UPLOAD',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS indexes (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  dataset_id UUID NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
  file_id UUID NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  index_type TEXT NOT NULL,
  object_key TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS searches (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  dataset_id UUID NOT NULL REFERENCES datasets(id),
  query TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'QUEUED',
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at TIMESTAMPTZ NULL
);

CREATE TABLE IF NOT EXISTS search_hits (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  search_id UUID NOT NULL REFERENCES searches(id) ON DELETE CASCADE,
  file_id UUID NOT NULL REFERENCES files(id),
  contig TEXT NULL,
  line_number INTEGER NULL,
  snippet TEXT NOT NULL,
  score DOUBLE PRECISION DEFAULT 1.0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_datasets_tenant ON datasets(tenant_id);
CREATE INDEX IF NOT EXISTS idx_files_tenant_dataset ON files(tenant_id, dataset_id);
CREATE INDEX IF NOT EXISTS idx_indexes_dataset ON indexes(dataset_id);
CREATE INDEX IF NOT EXISTS idx_search_hits_search ON search_hits(search_id);

ALTER TABLE datasets ENABLE ROW LEVEL SECURITY;
ALTER TABLE files ENABLE ROW LEVEL SECURITY;
ALTER TABLE indexes ENABLE ROW LEVEL SECURITY;
ALTER TABLE searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_hits ENABLE ROW LEVEL SECURITY;
```

---

## `libs/genomics_common/config.py`

```python
import os


class Settings:
    service_name = os.getenv("SERVICE_NAME", "genomics-service")

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://genomics:genomics@postgresql:5432/genomics",
    )

    kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    kafka_ingest_topic = os.getenv("KAFKA_INGEST_TOPIC", "genomics.ingest.requested")
    kafka_indexed_topic = os.getenv("KAFKA_INDEXED_TOPIC", "genomics.ingest.indexed")
    kafka_search_topic = os.getenv("KAFKA_SEARCH_TOPIC", "genomics.search.jobs")

    s3_endpoint_url = os.getenv("S3_ENDPOINT_URL", "http://minio:9000")
    s3_access_key = os.getenv("S3_ACCESS_KEY", "minioadmin")
    s3_secret_key = os.getenv("S3_SECRET_KEY", "minioadmin")
    s3_bucket = os.getenv("S3_BUCKET", "genomics")

    jwt_secret = os.getenv("JWT_SECRET", "change-me")
    jwt_issuer = os.getenv("JWT_ISSUER", "genomics-platform")
    jwt_audience = os.getenv("JWT_AUDIENCE", "genomics-api")

    upload_max_bytes = int(os.getenv("UPLOAD_MAX_BYTES", str(50 * 1024 * 1024 * 1024)))

    otel_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")


settings = Settings()
```

---

## `libs/genomics_common/models.py`

```python
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
```

---

## `libs/genomics_common/db.py`

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings
from .models import Base

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=30,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    Base.metadata.create_all(bind=engine)


def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## `libs/genomics_common/auth.py`

```python
from dataclasses import dataclass
from typing import Iterable
import jwt
from fastapi import Header, HTTPException, status
from .config import settings


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: str
    roles: list[str]


def decode_token(token: str) -> Principal:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: {str(exc)}",
        )

    tenant_id = payload.get("tenant_id")
    subject = payload.get("sub")
    roles = payload.get("roles", [])

    if not tenant_id or not subject:
        raise HTTPException(status_code=401, detail="token missing tenant_id or sub")

    return Principal(subject=subject, tenant_id=tenant_id, roles=list(roles))


def require_principal(authorization: str = Header(...)) -> Principal:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    return decode_token(authorization.removeprefix("Bearer ").strip())


def require_roles(principal: Principal, allowed: Iterable[str]):
    if not set(principal.roles).intersection(set(allowed)):
        raise HTTPException(status_code=403, detail="insufficient role")
```

---

## `libs/genomics_common/genomics.py`

```python
import os
import re
from fastapi import HTTPException

ALLOWED_KINDS = {"FASTA", "FASTQ", "BAM", "VCF"}

EXTENSION_KIND = {
    ".fa": "FASTA",
    ".fasta": "FASTA",
    ".fna": "FASTA",
    ".fq": "FASTQ",
    ".fastq": "FASTQ",
    ".bam": "BAM",
    ".vcf": "VCF",
    ".vcf.gz": "VCF",
}


SAFE_FILENAME = re.compile(r"^[A-Za-z0-9._+-]+$")


def safe_filename(filename: str) -> str:
    base = os.path.basename(filename)

    if base != filename or not SAFE_FILENAME.match(base):
        raise HTTPException(status_code=400, detail="unsafe filename")

    return base


def detect_kind(filename: str) -> str:
    lowered = filename.lower()

    for ext, kind in EXTENSION_KIND.items():
        if lowered.endswith(ext):
            return kind

    raise HTTPException(status_code=400, detail="unsupported genomic file type")


def validate_declared_kind(filename: str, declared: str | None) -> str:
    detected = detect_kind(filename)

    if declared and declared.upper() != detected:
        raise HTTPException(status_code=400, detail="declared kind does not match extension")

    return detected
```

---

## `libs/genomics_common/storage.py`

```python
import boto3
from botocore.client import Config
from .config import settings


def s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket():
    s3 = s3_client()
    buckets = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
    if settings.s3_bucket not in buckets:
        s3.create_bucket(Bucket=settings.s3_bucket)


def presigned_put(object_key: str, content_type: str = "application/octet-stream", expires: int = 3600):
    s3 = s3_client()
    return s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.s3_bucket,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=expires,
    )


def presigned_get(object_key: str, expires: int = 3600):
    s3 = s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": object_key},
        ExpiresIn=expires,
    )
```

---

## `libs/genomics_common/events.py`

```python
import json
from confluent_kafka import Producer, Consumer
from .config import settings


def kafka_producer():
    return Producer({"bootstrap.servers": settings.kafka_bootstrap_servers})


def publish(topic: str, key: str, value: dict):
    producer = kafka_producer()
    producer.produce(topic, key=key, value=json.dumps(value).encode("utf-8"))
    producer.flush(10)


def kafka_consumer(group_id: str, topics: list[str]):
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe(topics)
    return consumer
```

---

## `libs/genomics_common/observability.py`

```python
from fastapi import FastAPI, Response
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

REQUESTS = Counter(
    "genomics_http_requests_total",
    "Total HTTP requests",
    ["service", "method", "path", "status"],
)

LATENCY = Histogram(
    "genomics_http_request_duration_seconds",
    "HTTP request latency",
    ["service", "method", "path"],
)


def instrument(app: FastAPI, service_name: str):
    FastAPIInstrumentor.instrument_app(app)

    @app.middleware("http")
    async def metrics_middleware(request, call_next):
        with LATENCY.labels(service_name, request.method, request.url.path).time():
            response = await call_next(request)
        REQUESTS.labels(service_name, request.method, request.url.path, response.status_code).inc()
        return response

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

---

# 4. Microservices

## `services/api-gateway/app.py`

```python
import os
import httpx
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import Response
from genomics_common.auth import require_principal, Principal
from genomics_common.observability import instrument

SERVICE_MAP = {
    "uploads": os.getenv("UPLOAD_SERVICE_URL", "http://upload-service:8080"),
    "search": os.getenv("SEARCH_SERVICE_URL", "http://search-service:8080"),
}

app = FastAPI(title="Genomics API Gateway")
instrument(app, "api-gateway")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.api_route("/{service}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(
    service: str,
    path: str,
    request: Request,
    principal: Principal = Depends(require_principal),
):
    if service not in SERVICE_MAP:
        raise HTTPException(status_code=404, detail="unknown service")

    upstream = f"{SERVICE_MAP[service]}/{path}"

    headers = dict(request.headers)
    headers["x-principal-sub"] = principal.subject
    headers["x-principal-tenant"] = principal.tenant_id
    headers["x-principal-roles"] = ",".join(principal.roles)

    body = await request.body()

    async with httpx.AsyncClient(timeout=120.0) as client:
        res = await client.request(
            request.method,
            upstream,
            params=request.query_params,
            content=body,
            headers=headers,
        )

    return Response(
        content=res.content,
        status_code=res.status_code,
        headers={
            k: v
            for k, v in res.headers.items()
            if k.lower() not in {"content-encoding", "transfer-encoding", "connection"}
        },
    )
```

---

## `services/upload-service/app.py`

```python
from uuid import uuid4
from pydantic import BaseModel, Field
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from genomics_common.auth import Principal, require_principal, require_roles
from genomics_common.config import settings
from genomics_common.db import db_session, init_db
from genomics_common.events import publish
from genomics_common.genomics import safe_filename, validate_declared_kind
from genomics_common.models import Tenant, Dataset, GenomicFile
from genomics_common.observability import instrument
from genomics_common.storage import ensure_bucket, presigned_put, s3_client

app = FastAPI(title="Secure Genomic Upload Service")
instrument(app, "upload-service")


class InitUploadRequest(BaseModel):
    dataset_name: str = Field(min_length=1, max_length=200)
    filename: str
    kind: str | None = None
    checksum_sha256: str | None = None
    size_bytes: int = Field(gt=0)
    parent_dataset_id: str | None = None


class CompleteUploadRequest(BaseModel):
    file_id: str


@app.on_event("startup")
def startup():
    init_db()
    ensure_bucket()


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


def ensure_tenant(db: Session, tenant_id: str):
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        tenant = Tenant(id=tenant_id, name=f"tenant-{tenant_id}")
        db.add(tenant)
        db.commit()
    return tenant


@app.post("/init")
def init_upload(
    req: InitUploadRequest,
    principal: Principal = Depends(require_principal),
    db: Session = Depends(db_session),
):
    require_roles(principal, ["researcher", "admin", "uploader"])

    if req.size_bytes > settings.upload_max_bytes:
        raise HTTPException(status_code=413, detail="file too large")

    filename = safe_filename(req.filename)
    kind = validate_declared_kind(filename, req.kind)

    ensure_tenant(db, principal.tenant_id)

    latest_version = (
        db.query(func.max(Dataset.version))
        .filter(Dataset.tenant_id == principal.tenant_id, Dataset.name == req.dataset_name)
        .scalar()
    )

    version = 1 if latest_version is None else latest_version + 1

    dataset = Dataset(
        tenant_id=principal.tenant_id,
        name=req.dataset_name,
        version=version,
        parent_dataset_id=req.parent_dataset_id,
        status="CREATED",
        created_by=principal.subject,
    )

    db.add(dataset)
    db.flush()

    object_key = f"tenants/{principal.tenant_id}/datasets/{dataset.id}/v{version}/raw/{uuid4()}-{filename}"

    genomic_file = GenomicFile(
        tenant_id=principal.tenant_id,
        dataset_id=dataset.id,
        object_key=object_key,
        filename=filename,
        kind=kind,
        checksum_sha256=req.checksum_sha256,
        size_bytes=req.size_bytes,
        status="PENDING_UPLOAD",
    )

    db.add(genomic_file)
    db.commit()

    upload_url = presigned_put(object_key)

    return {
        "dataset_id": dataset.id,
        "version": version,
        "file_id": genomic_file.id,
        "object_key": object_key,
        "upload_url": upload_url,
        "method": "PUT",
        "headers": {"Content-Type": "application/octet-stream"},
    }


@app.post("/complete")
def complete_upload(
    req: CompleteUploadRequest,
    principal: Principal = Depends(require_principal),
    db: Session = Depends(db_session),
):
    require_roles(principal, ["researcher", "admin", "uploader"])

    file = (
        db.query(GenomicFile)
        .filter(GenomicFile.id == req.file_id, GenomicFile.tenant_id == principal.tenant_id)
        .first()
    )

    if not file:
        raise HTTPException(status_code=404, detail="file not found")

    s3 = s3_client()

    try:
        head = s3.head_object(Bucket=settings.s3_bucket, Key=file.object_key)
    except Exception:
        raise HTTPException(status_code=400, detail="uploaded object not found")

    if head.get("ContentLength", 0) <= 0:
        raise HTTPException(status_code=400, detail="empty object")

    file.status = "UPLOADED"

    dataset = (
        db.query(Dataset)
        .filter(Dataset.id == file.dataset_id, Dataset.tenant_id == principal.tenant_id)
        .first()
    )
    dataset.status = "UPLOADED"

    db.commit()

    publish(
        settings.kafka_ingest_topic,
        key=file.id,
        value={
            "event_type": "ingest.requested",
            "tenant_id": principal.tenant_id,
            "dataset_id": file.dataset_id,
            "file_id": file.id,
            "object_key": file.object_key,
            "kind": file.kind,
        },
    )

    return {"status": "queued_for_indexing", "file_id": file.id, "dataset_id": file.dataset_id}
```

---

## `services/indexer-worker/app.py`

```python
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from genomics_common.config import settings
from genomics_common.db import SessionLocal, init

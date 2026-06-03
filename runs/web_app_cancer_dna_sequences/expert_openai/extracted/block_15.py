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

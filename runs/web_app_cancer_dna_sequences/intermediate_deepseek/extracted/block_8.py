import json, uuid, os
from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form, File
from sqlalchemy.orm import Session
from app import auth, models, schemas
from app.database import SessionLocal
from app.utils.validator import detect_file_type, validate_fasta, validate_fastq
from app.tasks import process_upload
from app.config import UPLOAD_DIR

router = APIRouter(prefix="/upload", tags=["uploads"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=schemas.UploadOut)
async def upload_file(
    file: UploadFile = File(...),
    metadata: str = Form("{}"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    # 1. Validate file type
    ft = detect_file_type(file.filename)
    if not ft:
        raise HTTPException(400, "Unsupported file type. Only .fasta/.fa/.fastq accepted.")
    # 2. Quick content validation (first few lines)
    content_sample = (await file.read(4096)).decode("utf-8", errors="ignore")
    await file.seek(0)  # reset
    if ft == "fasta":
        ok, err = validate_fasta(content_sample)
    else:
        ok, err = validate_fastq(content_sample)
    if not ok:
        raise HTTPException(400, f"Invalid {ft} file: {err}")
    # 3. Save file to storage
    file_id = str(uuid.uuid4())
    storage_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with open(storage_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            f.write(chunk)
    # 4. Parse metadata JSON
    try:
        meta = json.loads(metadata)
    except json.JSONDecodeError:
        meta = {}
    # 5. Create upload record
    upload = models.Upload(
        user_id=current_user.id,
        filename=file_id + "_" + file.filename,
        original_filename=file.filename,
        file_type=ft,
        storage_path=storage_path,
        metadata_json=meta,
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    # 6. Queue background processing
    process_upload.delay(upload.id)
    return upload

@router.get("/", response_model=list[schemas.UploadOut])
def list_uploads(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return db.query(models.Upload).filter(models.Upload.user_id == current_user.id).all()

@router.get("/{upload_id}", response_model=schemas.UploadOut)
def get_upload(
    upload_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    upload = db.query(models.Upload).filter(
        models.Upload.id == upload_id,
        models.Upload.user_id == current_user.id,
    ).first()
    if not upload:
        raise HTTPException(404, "Upload not found")
    return upload

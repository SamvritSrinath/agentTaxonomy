from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app import auth, models, schemas
from app.database import SessionLocal

router = APIRouter(prefix="/sequences", tags=["sequences"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/", response_model=list[schemas.SequenceOut])
def list_sequences(
    upload_id: int = Query(..., description="Upload ID"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    # Ensure the upload belongs to the current user
    upload = db.query(models.Upload).filter(
        models.Upload.id == upload_id,
        models.Upload.user_id == current_user.id,
    ).first()
    if not upload:
        raise HTTPException(404, "Upload not found")
    sequences = (
        db.query(models.Sequence)
        .filter(models.Sequence.upload_id == upload_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return sequences

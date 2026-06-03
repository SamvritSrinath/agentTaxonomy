import hashlib
from sqlalchemy.orm import Session
from app.workers import celery_app
from app.database import SessionLocal, engine
from app import models
from app.utils.validator import validate_fasta, validate_fastq
import re

@celery_app.task(bind=True, max_retries=3)
def process_upload(self, upload_id: int):
    db = SessionLocal()
    try:
        upload = db.query(models.Upload).filter(models.Upload.id == upload_id).first()
        if not upload:
            return
        upload.status = models.UploadStatus.PROCESSING
        db.commit()

        # Read the whole file (assumes file sizes are manageable; for huge files use streaming)
        with open(upload.storage_path, "r") as f:
            content = f.read()

        # Full validation
        if upload.file_type == "fasta":
            ok, err = validate_fasta(content)
        else:
            ok, err = validate_fastq(content)
        if not ok:
            upload.status = models.UploadStatus.FAILED
            upload.metadata_json["error"] = err
            db.commit()
            return

        # Parse and index sequences
        seq_entries = parse_sequences(upload.file_type, content)
        for entry in seq_entries:
            seq_obj = models.Sequence(
                upload_id=upload.id,
                sequence_id=entry["seqid"],
                description=entry.get("description", ""),
                sequence=entry["sequence"],
                length=len(entry["sequence"]),
                quality=entry.get("quality"),
                md5=hashlib.md5(entry["sequence"].encode()).hexdigest(),
            )
            db.add(seq_obj)
        upload.status = models.UploadStatus.COMPLETED
        db.commit()
    except Exception as exc:
        upload.status = models.UploadStatus.FAILED
        db.commit()
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()

def parse_sequences(file_type, content):
    """Generator yielding sequence dictionaries from FASTA/FASTQ content."""
    if file_type == "fasta":
        # Simple FASTA parser (handles multi‑line sequences)
        pattern = re.compile(r'^>(\S+)\s*(.*)')
        current_header = None
        current_seq = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            m = pattern.match(line)
            if m:
                if current_header:
                    yield {"seqid": current_header, "description": current_desc,
                           "sequence": ''.join(current_seq)}
                current_header = m.group(1)
                current_desc = m.group(2) if m.group(2) else ""
                current_seq = []
            else:
                current_seq.append(line.upper())
        if current_header:
            yield {"seqid": current_header, "description": current_desc,
                   "sequence": ''.join(current_seq)}
    else:  # FASTQ
        lines = content.splitlines()
        i = 0
        while i < len(lines):
            if not lines[i].startswith('@'):
                i += 1
                continue
            header = lines[i][1:].strip()
            seq = lines[i+1].strip() if i+1 < len(lines) else ""
            plus = lines[i+2].strip() if i+2 < len(lines) else ""
            qual = lines[i+3].strip() if i+3 < len(lines) else ""
            yield {"seqid": header, "sequence": seq, "quality": qual}
            i += 4

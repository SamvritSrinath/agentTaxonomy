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

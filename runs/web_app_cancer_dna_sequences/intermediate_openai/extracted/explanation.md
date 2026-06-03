Below is a runnable modular FastAPI/PostgreSQL scaffold for a cancer genomics sequence-management platform with JWT login, FASTA/FASTQ upload validation, metadata/tags, and background sequence indexing.

---

## Project layout
---

## `requirements.txt`
---

## `.env.example`
---

## `Dockerfile`
---

## `docker-compose.yml`
---

# Backend source code

## `backend/app/core/config.py`
---

## `backend/app/core/security.py`
---

## `backend/app/db/session.py`
---

## `backend/app/db/base.py`
---

## `backend/app/models/user.py`
---

## `backend/app/models/sequence.py`
---

## `backend/app/schemas/auth.py`
---

## `backend/app/schemas/sequence.py`
---

## `backend/app/api/deps.py`
---

## `backend/app/services/validators.py`
---

## `backend/app/services/storage.py`
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

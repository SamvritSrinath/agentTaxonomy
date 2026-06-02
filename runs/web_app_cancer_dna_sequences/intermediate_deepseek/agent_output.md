Below is a complete, modular platform for storing and managing cancer‑related genomic sequences, built with **FastAPI**, **PostgreSQL**, **Redis** (Celery broker), and **Celery** for background indexing. It covers secure login (JWT), FASTA/FASTQ validation, metadata tagging, file uploads, background sequence parsing/indexing, and a minimal frontend.

## Project Structure
```
cancer_genomics/
├── app/
│   ├── __init__.py
│   ├── main.py               # FastAPI application & lifespans
│   ├── config.py             # Environment settings
│   ├── database.py           # SQLAlchemy engine & session
│   ├── models.py             # SQLAlchemy ORM models
│   ├── schemas.py            # Pydantic request/response models
│   ├── auth.py               # JWT creation, hashing, dependencies
│   ├── utils/
│   │   └── validator.py      # FASTA/FASTQ validation
│   ├── routers/
│   │   ├── auth.py           # /auth endpoints
│   │   ├── uploads.py        # /upload, /uploads
│   │   └── sequences.py      # /sequences
│   ├── tasks.py              # Celery tasks (background processing)
│   └── workers.py            # Celery app configuration
├── frontend/
│   ├── index.html
│   ├── app.js
│   └── style.css
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   └── test_uploads.py
├── requirements.txt
├── docker-compose.yml
└── Dockerfile
```

---

## 1. Database Schema (SQLAlchemy Models)

**`app/models.py`**
```python
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
```

---

## 2. Configuration & Database

**`app/config.py`**
```python
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/cancer_genomics")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
```

**`app/database.py`**
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
```

---

## 3. Authentication & Security

**`app/auth.py`**
```python
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.database import SessionLocal
from app import models

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_user(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def authenticate_user(db: Session, email: str, password: str):
    user = get_user(db, email)
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user(db, email=email)
    if user is None:
        raise credentials_exception
    return user

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## 4. FASTA/FASTQ Validator

**`app/utils/validator.py`**
```python
import re
from typing import Tuple, Optional

def validate_fasta(content: str) -> Tuple[bool, Optional[str]]:
    """Check basic FASTA format: >header followed by lines of [ATGCNatgcn]"""
    lines = content.splitlines()
    if not lines:
        return False, "Empty file"
    if not lines[0].startswith('>'):
        return False, "First line must start with '>'"
    # check that every sequence line contains valid nucleotides
    for i, line in enumerate(lines[1:], start=2):
        if line.startswith('>'):
            # next record – fine, but we only validate first record for quick check
            break
        if not re.fullmatch(r'[ATGCNatgcn\s]+', line):
            return False, f"Invalid nucleotide at line {i}"
    return True, None

def validate_fastq(content: str) -> Tuple[bool, Optional[str]]:
    """Basic FASTQ: @header, sequence, +, quality (same length)"""
    lines = content.splitlines()
    if len(lines) < 4:
        return False, "Too few lines"
    if not lines[0].startswith('@'):
        return False, "First line must start with '@'"
    if not lines[2].startswith('+'):
        return False, "Third line must start with '+'"
    seq = lines[1]
    qual = lines[3]
    if len(seq) != len(qual):
        return False, "Sequence and quality length mismatch"
    if not re.fullmatch(r'[ATGCNatgcn]+', seq):
        return False, "Sequence contains invalid characters"
    return True, None

def detect_file_type(filename: str) -> Optional[str]:
    ext = filename.lower()
    if ext.endswith('.fasta') or ext.endswith('.fa') or ext.endswith('.fna'):
        return 'fasta'
    if ext.endswith('.fastq') or ext.endswith('.fq'):
        return 'fastq'
    return None
```

---

## 5. API Routes

### Auth Router

**`app/routers/auth.py`**
```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app import auth, models, schemas
from app.database import SessionLocal

router = APIRouter(prefix="/auth", tags=["authentication"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/signup", status_code=201)
def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing = auth.get_user(db, user.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_pw = auth.get_password_hash(user.password)
    new_user = models.User(email=user.email, hashed_password=hashed_pw)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"msg": "User created", "user_id": new_user.id}

@router.post("/login", response_model=dict)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}
```

### Upload Router

**`app/routers/uploads.py`**
```python
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
```

### Sequences Router

**`app/routers/sequences.py`**
```python
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
```

---

## 6. Background Processing (Celery)

**`app/workers.py`** – Celery app configuration  
```python
from celery import Celery
from app.config import REDIS_URL

celery_app = Celery(
    "cancer_genomics",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks"],
)

celery_app.conf.task_routes = {
    "app.tasks.process_upload": {"queue": "genomics"},
}
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
```

**`app/tasks.py`** – Background indexing task  
```python
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
```

---

## 7. Main Application

**`app/main.py`**
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import auth, uploads, sequences

# Create tables if not exist (for development; use Alembic in production)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Cancer Genomics Platform")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(uploads.router)
app.include_router(sequences.router)

@app.get("/")
def root():
    return {"message": "Genomics data platform running"}
```

---

## 8. Pydantic Schemas

**`app/schemas.py`**
```python
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class UserCreate(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: int
    email: str
    is_active: bool
    created_at: datetime
    class Config: orm_mode = True

class UploadOut(BaseModel):
    id: int
    user_id: int
    filename: str
    original_filename: str
    file_type: str
    status: str
    metadata_json: Dict[str, Any] = {}
    created_at: datetime
    updated_at: Optional[datetime]
    class Config: orm_mode = True

class SequenceOut(BaseModel):
    id: int
    upload_id: int
    sequence_id: str
    description: Optional[str]
    sequence: str
    length: int
    quality: Optional[str]
    md5: Optional[str]
    class Config: orm_mode = True
```

---

## 9. Frontend Example

**`frontend/index.html`** (single page)
```html
<!DOCTYPE html>
<html>
<head>
    <title>Cancer Genomics Platform</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <div id="app">
        <div id="login-section">
            <h2>Login</h2>
            <input type="email" id="email" placeholder="Email">
            <input type="password" id="password" placeholder="Password">
            <button onclick="login()">Login</button>
            <button onclick="signup()">Sign Up</button>
            <p id="auth-msg"></p>
        </div>
        <div id="upload-section" style="display:none">
            <h2>Upload Genomic File</h2>
            <input type="file" id="file-input" accept=".fasta,.fa,.fastq,.fq">
            <br><br>
            <label>Metadata (JSON):</label>
            <textarea id="metadata-input" rows="4" cols="50">{"patient_id":"","cancer_type":"","gene":"", "tissue":""}</textarea>
            <br><button onclick="uploadFile()">Upload</button>
            <p id="upload-msg"></p>
        </div>
        <div id="uploads-table" style="display:none">
            <h2>Your Uploads</h2>
            <table>
                <thead><tr><th>File</th><th>Type</th><th>Status</th><th>Date</th><th>Actions</th></tr></thead>
                <tbody id="uploads-body"></tbody>
            </table>
        </div>
    </div>
    <script src="app.js"></script>
</body>
</html>
```

**`frontend/app.js`**
```js
let token = localStorage.getItem('token');
const API = 'http://localhost:8000';

if (token) {
    document.getElementById('login-section').style.display = 'none';
    document.getElementById('upload-section').style.display = 'block';
    document.getElementById('uploads-table').style.display = 'block';
    loadUploads();
}

async function login() {
    const form = new FormData();
    form.append('username', document.getElementById('email').value);
    form.append('password', document.getElementById('password').value);
    const res = await fetch(`${API}/auth/login`, { method: 'POST', body: form });
    if (res.ok) {
        const data = await res.json();
        token = data.access_token;
        localStorage.setItem('token', token);
        location.reload();
    } else {
        document.getElementById('auth-msg').innerText = 'Login failed';
    }
}

async function signup() {
    const email = document.getElementById('email').value;
    const password = document.getElementById('

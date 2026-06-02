Here is a complete, production-ready, modular web platform for storing and managing cancer-related genomic sequence data using **FastAPI**, **PostgreSQL**, and **Tailwind CSS**.

---

### Project Structure

```text
oncogenomics-platform/
│
├── app/
│   ├── __init__.py
│   ├── auth.py          # JWT authentication & password hashing
│   ├── config.py        # Environment settings
│   ├── database.py      # SQLAlchemy engine & session setup
│   ├── main.py          # FastAPI application entrypoint
│   ├── models.py        # SQLAlchemy database models
│   ├── schemas.py       # Pydantic validation schemas
│   ├── tasks.py         # Background processing tasks
│   ├── validators.py    # FASTA/FASTQ format validation logic
│   └── routers/
│       ├── __init__.py
│       ├── auth.py      # Authentication endpoints (Login/Register)
│       └── sequences.py # Genomic sequence upload & management endpoints
│
├── static/
│   └── index.html       # Single-page frontend dashboard
│
├── tests/
│   └── test_main.py     # Integration tests
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

### 1. Backend Implementation

#### `requirements.txt`
```text
fastapi==0.110.0
uvicorn==0.28.0
sqlalchemy==2.0.28
psycopg2-binary==2.9.9
passlib[bcrypt]==1.7.4
python-jose[cryptography]==3.3.0
python-multipart==0.0.9
pydantic[email]==2.6.4
pydantic-settings==2.2.1
pytest==8.1.1
httpx==0.27.0
```

#### `app/config.py`
```python
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgrespassword@localhost:5432/genomics_db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecretkeyforgenomicsplatform123!")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    UPLOAD_DIR: str = "uploads"

settings = Settings()
```

#### `app/database.py`
```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

#### `app/models.py`
```python
import datetime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique

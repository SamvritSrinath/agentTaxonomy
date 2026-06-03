import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/cancer_genomics")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SECRET_KEY = os.getenv("SECRET_KEY", "change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")

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

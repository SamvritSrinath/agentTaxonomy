from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from auth import verify_token, get_current_user
from opa_middleware import OPAMiddleware
import httpx

app = FastAPI(title="Genomic Platform API Gateway")

# CORS for researcher frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inject OPA middleware (sidecar via Unix socket or HTTP)
opa_middleware = OPAMiddleware("http://opa:8181/v1/data/genomics/authz")
app.middleware("http")(opa_middleware.authz_middleware)

# Define protected routes
# Forwarding to ingestion service (internal k8s DNS)
ingestion_service_url = "http://ingestion-service:8080"

@app.post("/api/v1/upload")
async def upload_file(request: Request, user: dict = Depends(get_current_user)):
    # OPA enforced; user and tenant already in request.state
    tenant = request.state.user["tenant"]
    data = await request.json()
    # Validate file metadata, then forward
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{ingestion_service_url}/upload", json={
            "tenant": tenant,
            "user_id": user["sub"],
            "file": data["file"]
        })
    return resp.json()

@app.get("/api/v1/datasets")
async def list_datasets(tenant: str = Depends(get_current_user)):
    # Gateway queries PostgreSQL directly (or via dataset service)
    pass
